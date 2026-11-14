"""Parallel Numba kernels for Earth-terrain normals, horizons, and illumination."""

from __future__ import annotations

import math

import numpy as np

RAY_NO_DATA = -1
RAY_UNKNOWN = 0
RAY_SEARCH_LIMIT = 1
RAY_OBSTRUCTION = 2
RAY_DEM_BOUNDARY = 3
RAY_TERRAIN_NODATA = 4
RAY_NORMAL_BOUNDARY = 5
RAY_NORMAL_NODATA = 6
RAY_SURFACE_AWAY = 7
RAY_VERTICAL_SUN = 8

try:
    from numba import njit, prange
except ImportError:  # pragma: no cover - depends on optional performance extra
    njit = None
    prange = None


def is_available() -> bool:
    return njit is not None


if njit is not None:

    @njit(cache=True)
    def _basis(longitude_rad, latitude_rad):
        sin_lon = math.sin(longitude_rad)
        cos_lon = math.cos(longitude_rad)
        sin_lat = math.sin(latitude_rad)
        cos_lat = math.cos(latitude_rad)
        return (
            -sin_lon, cos_lon, 0.0,
            -sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat,
            cos_lat * cos_lon, cos_lat * sin_lon, sin_lat,
        )

    @njit(cache=True)
    def _ecef(longitude_deg, latitude_deg, elevation_m, semi_major_m, inverse_flattening):
        longitude = longitude_deg * (math.pi / 180.0)
        latitude = latitude_deg * (math.pi / 180.0)
        flattening = 1.0 / inverse_flattening
        eccentricity_squared = flattening * (2.0 - flattening)
        sin_latitude = math.sin(latitude)
        cos_latitude = math.cos(latitude)
        prime_vertical = semi_major_m / math.sqrt(
            1.0 - eccentricity_squared * sin_latitude * sin_latitude
        )
        return (
            (prime_vertical + elevation_m) * cos_latitude * math.cos(longitude),
            (prime_vertical + elevation_m) * cos_latitude * math.sin(longitude),
            (prime_vertical * (1.0 - eccentricity_squared) + elevation_m) * sin_latitude,
        )

    @njit(cache=True)
    def _normal_at(elevations, longitudes, latitudes, row, col, radius_pixels,
                   semi_major_m, inverse_flattening):
        height, width = elevations.shape
        center_elevation = elevations[row, col]
        if not math.isfinite(center_elevation):
            return 0.0, 0.0, 0.0, False
        west_col = col - radius_pixels
        east_col = col + radius_pixels
        north_row = row - radius_pixels
        south_row = row + radius_pixels
        if (west_col < 0 or east_col >= width or north_row < 0 or south_row >= height):
            return 0.0, 0.0, 0.0, False
        if not (
            math.isfinite(elevations[row, west_col])
            and math.isfinite(elevations[row, east_col])
            and math.isfinite(elevations[north_row, col])
            and math.isfinite(elevations[south_row, col])
        ):
            return 0.0, 0.0, 0.0, False

        west = _ecef(longitudes[row, west_col], latitudes[row, west_col],
                     0.0, semi_major_m, inverse_flattening)
        east = _ecef(longitudes[row, east_col], latitudes[row, east_col],
                     0.0, semi_major_m, inverse_flattening)
        north = _ecef(longitudes[north_row, col], latitudes[north_row, col],
                      0.0, semi_major_m, inverse_flattening)
        south = _ecef(longitudes[south_row, col], latitudes[south_row, col],
                      0.0, semi_major_m, inverse_flattening)
        longitude = longitudes[row, col] * (math.pi / 180.0)
        latitude = latitudes[row, col] * (math.pi / 180.0)
        _, _, _, _, _, _, up_x, up_y, up_z = _basis(longitude, latitude)
        center = _ecef(
            longitudes[row, col], latitudes[row, col], 0.0,
            semi_major_m, inverse_flattening,
        )
        west_delta = (
            west[0] - center[0] + (elevations[row, west_col] - center_elevation) * up_x,
            west[1] - center[1] + (elevations[row, west_col] - center_elevation) * up_y,
            west[2] - center[2] + (elevations[row, west_col] - center_elevation) * up_z,
        )
        east_delta = (
            east[0] - center[0] + (elevations[row, east_col] - center_elevation) * up_x,
            east[1] - center[1] + (elevations[row, east_col] - center_elevation) * up_y,
            east[2] - center[2] + (elevations[row, east_col] - center_elevation) * up_z,
        )
        north_delta = (
            north[0] - center[0] + (elevations[north_row, col] - center_elevation) * up_x,
            north[1] - center[1] + (elevations[north_row, col] - center_elevation) * up_y,
            north[2] - center[2] + (elevations[north_row, col] - center_elevation) * up_z,
        )
        south_delta = (
            south[0] - center[0] + (elevations[south_row, col] - center_elevation) * up_x,
            south[1] - center[1] + (elevations[south_row, col] - center_elevation) * up_y,
            south[2] - center[2] + (elevations[south_row, col] - center_elevation) * up_z,
        )
        tangent_col_x = east_delta[0] - west_delta[0]
        tangent_col_y = east_delta[1] - west_delta[1]
        tangent_col_z = east_delta[2] - west_delta[2]
        tangent_row_x = south_delta[0] - north_delta[0]
        tangent_row_y = south_delta[1] - north_delta[1]
        tangent_row_z = south_delta[2] - north_delta[2]
        normal_x = tangent_col_y * tangent_row_z - tangent_col_z * tangent_row_y
        normal_y = tangent_col_z * tangent_row_x - tangent_col_x * tangent_row_z
        normal_z = tangent_col_x * tangent_row_y - tangent_col_y * tangent_row_x
        if normal_x * up_x + normal_y * up_y + normal_z * up_z < 0.0:
            normal_x = -normal_x
            normal_y = -normal_y
            normal_z = -normal_z
        norm = math.sqrt(normal_x * normal_x + normal_y * normal_y + normal_z * normal_z)
        if not math.isfinite(norm) or norm <= 1e-12:
            return 0.0, 0.0, 0.0, False
        return normal_x / norm, normal_y / norm, normal_z / norm, True

    @njit(cache=True, parallel=True)
    def compute_normals(elevations, longitudes, latitudes, radius_pixels,
                        semi_major_m, inverse_flattening):
        height, width = elevations.shape
        normals = np.zeros((height, width, 3), dtype=np.float64)
        valid = np.zeros((height, width), dtype=np.bool_)
        for row in prange(height):
            for col in range(width):
                nx, ny, nz, ok = _normal_at(
                    elevations, longitudes, latitudes, row, col, radius_pixels,
                    semi_major_m, inverse_flattening,
                )
                if ok:
                    normals[row, col, 0] = nx
                    normals[row, col, 1] = ny
                    normals[row, col, 2] = nz
                    valid[row, col] = True
        return normals, valid

    @njit(cache=True)
    def _evaluate_cell(elevations, row, col, distance_m, center_elevation,
                       east_component, north_component, solar_elevation_rad,
                       meridional_radius_m, prime_vertical_radius_m,
                       obstruction_tolerance_m, check_sun):
        row = int(row)
        col = int(col)
        height, width = elevations.shape
        if row < 0 or row >= height or col < 0 or col >= width:
            return RAY_DEM_BOUNDARY, False, -math.inf
        terrain_elevation = elevations[row, col]
        if not math.isfinite(terrain_elevation):
            return RAY_TERRAIN_NODATA, False, -math.inf
        if distance_m <= 0.0:
            return RAY_UNKNOWN, False, -math.inf
        east_distance = distance_m * east_component
        north_distance = distance_m * north_component
        curvature_drop = 0.5 * (
            east_distance * east_distance / prime_vertical_radius_m
            + north_distance * north_distance / meridional_radius_m
        )
        relative_height = terrain_elevation - center_elevation - curvature_drop
        apparent = math.atan2(relative_height, distance_m)
        blocked = False
        if check_sun:
            ray_height = distance_m * math.tan(solar_elevation_rad)
            blocked = relative_height > ray_height + obstruction_tolerance_m
        return RAY_UNKNOWN, blocked, apparent

    @njit(cache=True)
    def _trace_ray(elevations, longitudes, latitudes, row, col, azimuth_rad,
                   solar_elevation_rad, check_sun, max_distance_m,
                   semi_major_m, inverse_flattening, obstruction_tolerance_m):
        row = int(row)
        col = int(col)
        height, width = elevations.shape
        if not math.isfinite(elevations[row, col]):
            return RAY_NO_DATA, False, 0.0, 0, -math.inf

        radius_pixels = 1
        if (row - radius_pixels < 0 or row + radius_pixels >= height
                or col - radius_pixels < 0 or col + radius_pixels >= width):
            return RAY_NORMAL_BOUNDARY, False, 0.0, 0, -math.inf
        if not (
            math.isfinite(elevations[row - 1, col])
            and math.isfinite(elevations[row + 1, col])
            and math.isfinite(elevations[row, col - 1])
            and math.isfinite(elevations[row, col + 1])
        ):
            return RAY_NORMAL_NODATA, False, 0.0, 0, -math.inf

        longitude = longitudes[row, col] * (math.pi / 180.0)
        latitude = latitudes[row, col] * (math.pi / 180.0)
        east_x, east_y, east_z, north_x, north_y, north_z, up_x, up_y, up_z = _basis(
            longitude, latitude
        )
        east_component = math.sin(azimuth_rad)
        north_component = math.cos(azimuth_rad)

        center_elevation = elevations[row, col]
        west_x, west_y, west_z = _ecef(
            longitudes[row, col - 1], latitudes[row, col - 1], 0.0,
            semi_major_m, inverse_flattening,
        )
        east2_x, east2_y, east2_z = _ecef(
            longitudes[row, col + 1], latitudes[row, col + 1], 0.0,
            semi_major_m, inverse_flattening,
        )
        north2_x, north2_y, north2_z = _ecef(
            longitudes[row - 1, col], latitudes[row - 1, col], 0.0,
            semi_major_m, inverse_flattening,
        )
        south_x, south_y, south_z = _ecef(
            longitudes[row + 1, col], latitudes[row + 1, col], 0.0,
            semi_major_m, inverse_flattening,
        )
        col_east = ((east2_x - west_x) * east_x + (east2_y - west_y) * east_y
                    + (east2_z - west_z) * east_z) * 0.5
        col_north = ((east2_x - west_x) * north_x + (east2_y - west_y) * north_y
                     + (east2_z - west_z) * north_z) * 0.5
        row_east = ((south_x - north2_x) * east_x + (south_y - north2_y) * east_y
                    + (south_z - north2_z) * east_z) * 0.5
        row_north = ((south_x - north2_x) * north_x + (south_y - north2_y) * north_y
                     + (south_z - north2_z) * north_z) * 0.5
        determinant = col_east * row_north - row_east * col_north
        if not math.isfinite(determinant) or abs(determinant) <= 1e-12:
            return RAY_UNKNOWN, False, 0.0, 0, -math.inf
        col_per_m = (east_component * row_north - row_east * north_component) / determinant
        row_per_m = (col_east * north_component - col_north * east_component) / determinant

        flattening = 1.0 / inverse_flattening
        eccentricity_squared = flattening * (2.0 - flattening)
        sin_latitude = math.sin(latitude)
        denominator = 1.0 - eccentricity_squared * sin_latitude * sin_latitude
        meridional_radius = semi_major_m * (1.0 - eccentricity_squared) / (denominator ** 1.5)
        prime_vertical_radius = semi_major_m / math.sqrt(denominator)

        col_step = 1 if col_per_m > 0.0 else -1
        row_step = 1 if row_per_m > 0.0 else -1
        col_rate = abs(col_per_m)
        row_rate = abs(row_per_m)
        col_delta = math.inf if col_rate <= 1e-15 else 1.0 / col_rate
        row_delta = math.inf if row_rate <= 1e-15 else 1.0 / row_rate
        col_next = math.inf if col_rate <= 1e-15 else 0.5 / col_rate
        row_next = math.inf if row_rate <= 1e-15 else 0.5 / row_rate
        current_row = row
        current_col = col
        max_horizon_rad = -math.inf
        max_horizon_distance = 0.0
        samples = 0

        while True:
            next_distance = min(col_next, row_next)
            if next_distance > max_distance_m:
                return RAY_SEARCH_LIMIT, False, max_horizon_distance, samples, max_horizon_rad

            tie = abs(col_next - row_next) <= 1e-10 * max(1.0, next_distance)
            if tie:
                check_col = current_col + col_step
                status, blocked, apparent = _evaluate_cell(
                    elevations, current_row, check_col, next_distance, center_elevation,
                    east_component, north_component, solar_elevation_rad,
                    meridional_radius, prime_vertical_radius,
                    obstruction_tolerance_m, check_sun,
                )
                if status == RAY_DEM_BOUNDARY or status == RAY_TERRAIN_NODATA:
                    return status, False, max_horizon_distance, samples, max_horizon_rad
                samples += 1
                if apparent > max_horizon_rad:
                    max_horizon_rad = apparent
                    max_horizon_distance = next_distance
                if blocked:
                    return RAY_OBSTRUCTION, True, max_horizon_distance, samples, max_horizon_rad

                check_row = current_row + row_step
                status, blocked, apparent = _evaluate_cell(
                    elevations, check_row, current_col, next_distance, center_elevation,
                    east_component, north_component, solar_elevation_rad,
                    meridional_radius, prime_vertical_radius,
                    obstruction_tolerance_m, check_sun,
                )
                if status == RAY_DEM_BOUNDARY or status == RAY_TERRAIN_NODATA:
                    return status, False, max_horizon_distance, samples, max_horizon_rad
                samples += 1
                if apparent > max_horizon_rad:
                    max_horizon_rad = apparent
                    max_horizon_distance = next_distance
                if blocked:
                    return RAY_OBSTRUCTION, True, max_horizon_distance, samples, max_horizon_rad

                status, blocked, apparent = _evaluate_cell(
                    elevations, check_row, check_col, next_distance, center_elevation,
                    east_component, north_component, solar_elevation_rad,
                    meridional_radius, prime_vertical_radius,
                    obstruction_tolerance_m, check_sun,
                )
                if status == RAY_DEM_BOUNDARY or status == RAY_TERRAIN_NODATA:
                    return status, False, max_horizon_distance, samples, max_horizon_rad
                samples += 1
                if apparent > max_horizon_rad:
                    max_horizon_rad = apparent
                    max_horizon_distance = next_distance
                if blocked:
                    return RAY_OBSTRUCTION, True, max_horizon_distance, samples, max_horizon_rad

                current_row = check_row
                current_col = check_col
                col_next += col_delta
                row_next += row_delta
            elif col_next < row_next:
                current_col += col_step
                next_distance = col_next
                col_next += col_delta
                status, blocked, apparent = _evaluate_cell(
                    elevations, current_row, current_col, next_distance, center_elevation,
                    east_component, north_component, solar_elevation_rad,
                    meridional_radius, prime_vertical_radius,
                    obstruction_tolerance_m, check_sun,
                )
                if status == RAY_DEM_BOUNDARY or status == RAY_TERRAIN_NODATA:
                    return status, False, max_horizon_distance, samples, max_horizon_rad
                samples += 1
                if apparent > max_horizon_rad:
                    max_horizon_rad = apparent
                    max_horizon_distance = next_distance
                if blocked:
                    return RAY_OBSTRUCTION, True, max_horizon_distance, samples, max_horizon_rad
            else:
                current_row += row_step
                next_distance = row_next
                row_next += row_delta
                status, blocked, apparent = _evaluate_cell(
                    elevations, current_row, current_col, next_distance, center_elevation,
                    east_component, north_component, solar_elevation_rad,
                    meridional_radius, prime_vertical_radius,
                    obstruction_tolerance_m, check_sun,
                )
                if status == RAY_DEM_BOUNDARY or status == RAY_TERRAIN_NODATA:
                    return status, False, next_distance, samples, max_horizon_rad
                samples += 1
                max_horizon_rad = max(max_horizon_rad, apparent)
                if blocked:
                    return RAY_OBSTRUCTION, True, next_distance, samples, max_horizon_rad

    @njit(cache=True, parallel=True)
    def classify_grid(elevations, longitudes, latitudes, normals, normal_valid,
                      sun_x, sun_y, sun_z, semi_major_m, inverse_flattening,
                      max_distance_m, tolerance, obstruction_tolerance_m):
        height, width = elevations.shape
        classes = np.full((height, width), 0, dtype=np.int16)
        ray_status = np.full((height, width), RAY_UNKNOWN, dtype=np.int8)
        coverage = np.zeros((height, width), dtype=np.bool_)
        valid = np.isfinite(elevations)
        sun_norm = math.sqrt(sun_x * sun_x + sun_y * sun_y + sun_z * sun_z)
        for row in prange(height):
            for col in range(width):
                if not valid[row, col]:
                    classes[row, col] = -1
                    ray_status[row, col] = RAY_NO_DATA
                    continue
                if not normal_valid[row, col]:
                    classes[row, col] = 4
                    if (row == 0 or col == 0 or row == height - 1 or col == width - 1):
                        ray_status[row, col] = RAY_NORMAL_BOUNDARY
                    else:
                        ray_status[row, col] = RAY_NORMAL_NODATA
                    continue
                if sun_norm <= 0.0 or not math.isfinite(sun_norm):
                    ray_status[row, col] = RAY_UNKNOWN
                    continue
                nx, ny, nz = normals[row, col, 0], normals[row, col, 1], normals[row, col, 2]
                dot = (nx * sun_x + ny * sun_y + nz * sun_z) / sun_norm
                if dot <= tolerance:
                    classes[row, col] = 3
                    ray_status[row, col] = RAY_SURFACE_AWAY
                    coverage[row, col] = True
                    continue

                longitude = longitudes[row, col] * (math.pi / 180.0)
                latitude = latitudes[row, col] * (math.pi / 180.0)
                east_x, east_y, east_z, north_x, north_y, north_z, up_x, up_y, up_z = _basis(
                    longitude, latitude
                )
                sun_east = sun_x * east_x + sun_y * east_y + sun_z * east_z
                sun_north = sun_x * north_x + sun_y * north_y + sun_z * north_z
                sun_up = sun_x * up_x + sun_y * up_y + sun_z * up_z
                horizontal = math.sqrt(sun_east * sun_east + sun_north * sun_north)
                if horizontal <= 1e-12:
                    if sun_up > 0.0:
                        classes[row, col] = 1
                        ray_status[row, col] = RAY_VERTICAL_SUN
                        coverage[row, col] = True
                    else:
                        classes[row, col] = 2
                        ray_status[row, col] = RAY_OBSTRUCTION
                        coverage[row, col] = True
                    continue
                azimuth = math.atan2(sun_east, sun_north)
                solar_elevation = math.atan2(sun_up, horizontal)
                status, blocked, distance, _, _ = _trace_ray(
                    elevations, longitudes, latitudes, int(row), int(col), azimuth,
                    solar_elevation, True, max_distance_m, semi_major_m,
                    inverse_flattening, obstruction_tolerance_m,
                )
                if status == RAY_OBSTRUCTION or blocked:
                    classes[row, col] = 2
                    ray_status[row, col] = RAY_OBSTRUCTION
                    coverage[row, col] = True
                elif status == RAY_SEARCH_LIMIT:
                    classes[row, col] = 1
                    ray_status[row, col] = RAY_SEARCH_LIMIT
                    coverage[row, col] = True
                elif status == RAY_DEM_BOUNDARY:
                    classes[row, col] = 4
                    ray_status[row, col] = RAY_DEM_BOUNDARY
                elif status == RAY_TERRAIN_NODATA:
                    classes[row, col] = 4
                    ray_status[row, col] = RAY_TERRAIN_NODATA
                else:
                    classes[row, col] = 0
                    ray_status[row, col] = status
        return classes, valid, normal_valid.copy(), coverage, ray_status

    @njit(cache=True, parallel=True)
    def horizon_rays(elevations, longitudes, latitudes, row, col, azimuths_rad,
                     semi_major_m, inverse_flattening, max_distance_m):
        count = azimuths_rad.size
        apparent = np.full(count, np.nan, dtype=np.float64)
        distance = np.full(count, np.nan, dtype=np.float64)
        status = np.full(count, RAY_UNKNOWN, dtype=np.int8)
        samples = np.zeros(count, dtype=np.int32)
        for index in prange(count):
            code, _, ray_distance, ray_samples, horizon = _trace_ray(
                elevations, longitudes, latitudes, row, col,
                azimuths_rad[index], 0.0, False, max_distance_m,
                semi_major_m, inverse_flattening, 0.0,
            )
            status[index] = code
            samples[index] = ray_samples
            if math.isfinite(horizon):
                apparent[index] = horizon * (180.0 / math.pi)
                distance[index] = ray_distance
        return apparent, distance, status, samples

else:

    def compute_normals(*args, **kwargs):
        raise RuntimeError("Numba is required for Earth terrain illumination; install the 'performance' extra")

    def classify_grid(*args, **kwargs):
        raise RuntimeError("Numba is required for Earth terrain illumination; install the 'performance' extra")

    def horizon_rays(*args, **kwargs):
        raise RuntimeError("Numba is required for Earth terrain illumination; install the 'performance' extra")
