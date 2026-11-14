"""Parallel Numba numerical kernels for lunar terrain illumination."""

from __future__ import annotations

import math

import numpy as np

RAY_STATUS_NO_DATA = -1
RAY_STATUS_UNKNOWN = 0
RAY_STATUS_SEARCH_LIMIT_REACHED = 1
RAY_STATUS_OBSTRUCTION_FOUND = 2
RAY_STATUS_DEM_BOUNDARY = 3
RAY_STATUS_TERRAIN_NODATA = 4
RAY_STATUS_SURFACE_FACING_AWAY = 5
RAY_STATUS_VERTICAL_SUN = 6

try:
    from numba import get_num_threads, njit, prange
except ImportError:  # pragma: no cover - depends on the optional performance extra
    njit = None
    get_num_threads = None


def is_available() -> bool:
    return njit is not None


def thread_count() -> int | None:
    return None if get_num_threads is None else int(get_num_threads())


if njit is not None:

    @njit(cache=True)
    def _basis(longitude_rad, latitude_rad):
        cos_lat = math.cos(latitude_rad)
        sin_lat = math.sin(latitude_rad)
        cos_lon = math.cos(longitude_rad)
        sin_lon = math.sin(longitude_rad)

        up_x = cos_lat * cos_lon
        up_y = cos_lat * sin_lon
        up_z = sin_lat

        east_x = -sin_lon
        east_y = cos_lon
        east_z = 0.0
        east_dot_up = east_x * up_x + east_y * up_y + east_z * up_z
        east_x -= east_dot_up * up_x
        east_y -= east_dot_up * up_y
        east_z -= east_dot_up * up_z
        east_norm = (east_x * east_x + east_y * east_y + east_z * east_z) ** 0.5
        if east_norm < 1e-12:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False
        east_x /= east_norm
        east_y /= east_norm
        east_z /= east_norm

        north_x = up_y * east_z - up_z * east_y
        north_y = up_z * east_x - up_x * east_z
        north_z = up_x * east_y - up_y * east_x
        north_norm = (north_x * north_x + north_y * north_y + north_z * north_z) ** 0.5
        if north_norm <= 0.0:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False
        north_x /= north_norm
        north_y /= north_norm
        north_z /= north_norm
        return (
            east_x, east_y, east_z,
            north_x, north_y, north_z,
            up_x, up_y, up_z,
            True,
        )

    @njit(cache=True)
    def _fixed_position(elevation, longitude_deg, latitude_deg, reference_radius_m):
        radius_km = (reference_radius_m + elevation) / 1000.0
        if radius_km <= 0.0:
            return 0.0, 0.0, 0.0, False
        longitude = longitude_deg * (math.pi / 180.0)
        latitude = latitude_deg * (math.pi / 180.0)
        cos_latitude = math.cos(latitude)
        return (
            radius_km * cos_latitude * math.cos(longitude),
            radius_km * cos_latitude * math.sin(longitude),
            radius_km * math.sin(latitude),
            True,
        )

    @njit(cache=True)
    def _normal_at(elevations, normal_longitudes, normal_latitudes,
                   row, col, row0, col0, reference_radius_m, radius_pixels):
        height, width = elevations.shape
        elevation = elevations[row, col]
        if not math.isfinite(elevation):
            return 0.0, 0.0, 0.0, False

        options = 0
        if col - radius_pixels >= 0 and math.isfinite(elevations[row, col - radius_pixels]):
            options += 1
        if col + radius_pixels < width and math.isfinite(elevations[row, col + radius_pixels]):
            options += 1
        if row - radius_pixels >= 0 and math.isfinite(elevations[row - radius_pixels, col]):
            options += 1
        if row + radius_pixels < height and math.isfinite(elevations[row + radius_pixels, col]):
            options += 1
        if options == 0:
            return 0.0, 0.0, 0.0, False

        local_row = row - row0 + radius_pixels
        local_col = col - col0 + radius_pixels
        center_longitude = normal_longitudes[local_row, local_col]
        center_latitude = normal_latitudes[local_row, local_col]
        center_x, center_y, center_z, center_valid = _fixed_position(
            elevation, center_longitude, center_latitude, reference_radius_m
        )
        if not center_valid:
            return 0.0, 0.0, 0.0, False

        west_valid = (
            col - radius_pixels >= 0
            and math.isfinite(elevations[row, col - radius_pixels])
        )
        east_valid = (
            col + radius_pixels < width
            and math.isfinite(elevations[row, col + radius_pixels])
        )
        north_valid = (
            row - radius_pixels >= 0
            and math.isfinite(elevations[row - radius_pixels, col])
        )
        south_valid = (
            row + radius_pixels < height
            and math.isfinite(elevations[row + radius_pixels, col])
        )

        west_elevation = (
            elevations[row, col - radius_pixels] if west_valid else elevation
        )
        east_elevation = (
            elevations[row, col + radius_pixels] if east_valid else elevation
        )
        north_elevation = (
            elevations[row - radius_pixels, col] if north_valid else elevation
        )
        south_elevation = (
            elevations[row + radius_pixels, col] if south_valid else elevation
        )

        west_x, west_y, west_z, west_position_valid = _fixed_position(
            west_elevation,
            normal_longitudes[local_row, local_col - radius_pixels],
            normal_latitudes[local_row, local_col - radius_pixels],
            reference_radius_m,
        )
        east_x, east_y, east_z, east_position_valid = _fixed_position(
            east_elevation,
            normal_longitudes[local_row, local_col + radius_pixels],
            normal_latitudes[local_row, local_col + radius_pixels],
            reference_radius_m,
        )
        north_x, north_y, north_z, north_position_valid = _fixed_position(
            north_elevation,
            normal_longitudes[local_row - radius_pixels, local_col],
            normal_latitudes[local_row - radius_pixels, local_col],
            reference_radius_m,
        )
        south_x, south_y, south_z, south_position_valid = _fixed_position(
            south_elevation,
            normal_longitudes[local_row + radius_pixels, local_col],
            normal_latitudes[local_row + radius_pixels, local_col],
            reference_radius_m,
        )
        if not (
            west_position_valid
            and east_position_valid
            and north_position_valid
            and south_position_valid
        ):
            return 0.0, 0.0, 0.0, False

        tangent_col_x = east_x - west_x
        tangent_col_y = east_y - west_y
        tangent_col_z = east_z - west_z
        tangent_row_x = south_x - north_x
        tangent_row_y = south_y - north_y
        tangent_row_z = south_z - north_z
        normal_x = tangent_col_y * tangent_row_z - tangent_col_z * tangent_row_y
        normal_y = tangent_col_z * tangent_row_x - tangent_col_x * tangent_row_z
        normal_z = tangent_col_x * tangent_row_y - tangent_col_y * tangent_row_x
        up_dot = normal_x * center_x + normal_y * center_y + normal_z * center_z
        if up_dot < 0.0:
            normal_x = -normal_x
            normal_y = -normal_y
            normal_z = -normal_z
        normal_norm = (normal_x * normal_x + normal_y * normal_y + normal_z * normal_z) ** 0.5
        if normal_norm <= 1e-15:
            return 0.0, 0.0, 0.0, False
        return normal_x / normal_norm, normal_y / normal_norm, normal_z / normal_norm, True

    @njit(cache=True, parallel=True)
    def compute_normal_window(elevations, normal_longitudes, normal_latitudes,
                              row0, col0, reference_radius_m, radius_pixels):
        rows = normal_longitudes.shape[0] - 2 * radius_pixels
        cols = normal_longitudes.shape[1] - 2 * radius_pixels
        normals = np.zeros((rows, cols, 3), dtype=np.float64)
        valid = np.zeros((rows, cols), dtype=np.bool_)
        for local_row in prange(rows):
            for local_col in range(cols):
                row = row0 + local_row
                col = col0 + local_col
                nx, ny, nz, is_valid = _normal_at(
                    elevations, normal_longitudes, normal_latitudes,
                    row, col, row0, col0, reference_radius_m, radius_pixels,
                )
                if is_valid:
                    normals[local_row, local_col, 0] = nx
                    normals[local_row, local_col, 1] = ny
                    normals[local_row, local_col, 2] = nz
                    valid[local_row, local_col] = True
        return normals, valid

    @njit(cache=True, parallel=True)
    def classify_window(elevations, longitudes, latitudes,
                        normal_longitudes, normal_latitudes, row0, col0,
                        transform, reference_radius_m, radius_pixels,
                        sun_x, sun_y, sun_z, sun_distance_km,
                        step_size_m, max_distance_m, tolerance,
                        cached_normals, cached_normal_valid, use_cache):
        rows, cols = longitudes.shape
        classification = np.full((rows, cols), -1, dtype=np.int16)
        normal_valid = np.zeros((rows, cols), dtype=np.bool_)
        coverage = np.zeros((rows, cols), dtype=np.bool_)
        ray_status = np.full((rows, cols), RAY_STATUS_UNKNOWN, dtype=np.int8)

        a, b, c, d, e, f = transform
        determinant = a * e - b * d
        inverse_det = 1.0 / determinant
        max_steps = max(1, int(max_distance_m / step_size_m))
        obstruction_threshold_m = max(1.0, 5.0 * step_size_m / 1000.0)
        pi_over_180 = math.pi / 180.0

        for local_row in prange(rows):
            row = row0 + local_row
            for local_col in range(cols):
                col = col0 + local_col
                elevation = elevations[row, col]
                if not math.isfinite(elevation):
                    classification[local_row, local_col] = -1
                    ray_status[local_row, local_col] = RAY_STATUS_NO_DATA
                    continue
                if use_cache:
                    if not cached_normal_valid[row, col]:
                        classification[local_row, local_col] = 0
                        continue
                    normal_x = cached_normals[row, col, 0]
                    normal_y = cached_normals[row, col, 1]
                    normal_z = cached_normals[row, col, 2]
                else:
                    normal_x, normal_y, normal_z, is_valid = _normal_at(
                        elevations, normal_longitudes, normal_latitudes,
                        row, col, row0, col0, reference_radius_m, radius_pixels,
                    )
                    if not is_valid:
                        classification[local_row, local_col] = 0
                        continue
                normal_valid[local_row, local_col] = True
                coverage[local_row, local_col] = True

                longitude = longitudes[local_row, local_col] * pi_over_180
                latitude = latitudes[local_row, local_col] * pi_over_180
                radius_km = (reference_radius_m + elevation) / 1000.0
                cos_lat = math.cos(latitude)
                site_x = radius_km * cos_lat * math.cos(longitude)
                site_y = radius_km * cos_lat * math.sin(longitude)
                site_z = radius_km * math.sin(latitude)
                if sun_distance_km > 0.0:
                    to_sun_x = sun_x * sun_distance_km - site_x
                    to_sun_y = sun_y * sun_distance_km - site_y
                    to_sun_z = sun_z * sun_distance_km - site_z
                else:
                    to_sun_x = sun_x
                    to_sun_y = sun_y
                    to_sun_z = sun_z
                to_sun_norm = math.sqrt(to_sun_x * to_sun_x + to_sun_y * to_sun_y + to_sun_z * to_sun_z)
                if to_sun_norm == 0.0:
                    classification[local_row, local_col] = 0
                    coverage[local_row, local_col] = False
                    continue
                to_sun_x /= to_sun_norm
                to_sun_y /= to_sun_norm
                to_sun_z /= to_sun_norm
                dot = normal_x * to_sun_x + normal_y * to_sun_y + normal_z * to_sun_z
                if dot <= tolerance:
                    classification[local_row, local_col] = 3
                    ray_status[local_row, local_col] = RAY_STATUS_SURFACE_FACING_AWAY
                    continue

                (east_x, east_y, east_z,
                 north_x, north_y, north_z,
                 up_x, up_y, up_z, basis_valid) = _basis(longitude, latitude)
                if not basis_valid:
                    classification[local_row, local_col] = 0
                    coverage[local_row, local_col] = False
                    continue
                sun_local_east = to_sun_x * east_x + to_sun_y * east_y + to_sun_z * east_z
                sun_local_north = to_sun_x * north_x + to_sun_y * north_y + to_sun_z * north_z
                horizontal_magnitude = math.sqrt(
                    sun_local_east * sun_local_east + sun_local_north * sun_local_north
                )
                if horizontal_magnitude <= tolerance:
                    classification[local_row, local_col] = 1
                    ray_status[local_row, local_col] = RAY_STATUS_VERTICAL_SUN
                    continue

                direction_x = sun_local_east / horizontal_magnitude
                direction_y = sun_local_north / horizontal_magnitude
                normal_row = local_row + radius_pixels
                normal_col = local_col + radius_pixels
                col_west_x, col_west_y, col_west_z, west_valid = _fixed_position(
                    elevation,
                    normal_longitudes[normal_row, normal_col - 1],
                    normal_latitudes[normal_row, normal_col - 1],
                    reference_radius_m,
                )
                col_east_x, col_east_y, col_east_z, east_valid = _fixed_position(
                    elevation,
                    normal_longitudes[normal_row, normal_col + 1],
                    normal_latitudes[normal_row, normal_col + 1],
                    reference_radius_m,
                )
                row_north_x, row_north_y, row_north_z, north_valid = _fixed_position(
                    elevation,
                    normal_longitudes[normal_row - 1, normal_col],
                    normal_latitudes[normal_row - 1, normal_col],
                    reference_radius_m,
                )
                row_south_x, row_south_y, row_south_z, south_valid = _fixed_position(
                    elevation,
                    normal_longitudes[normal_row + 1, normal_col],
                    normal_latitudes[normal_row + 1, normal_col],
                    reference_radius_m,
                )
                if not (west_valid and east_valid and north_valid and south_valid):
                    classification[local_row, local_col] = 0
                    coverage[local_row, local_col] = False
                    continue

                col_east = 500.0 * (
                    (col_east_x - col_west_x) * east_x
                    + (col_east_y - col_west_y) * east_y
                    + (col_east_z - col_west_z) * east_z
                )
                col_north = 500.0 * (
                    (col_east_x - col_west_x) * north_x
                    + (col_east_y - col_west_y) * north_y
                    + (col_east_z - col_west_z) * north_z
                )
                row_east = 500.0 * (
                    (row_south_x - row_north_x) * east_x
                    + (row_south_y - row_north_y) * east_y
                    + (row_south_z - row_north_z) * east_z
                )
                row_north = 500.0 * (
                    (row_south_x - row_north_x) * north_x
                    + (row_south_y - row_north_y) * north_y
                    + (row_south_z - row_north_z) * north_z
                )
                grid_determinant = col_east * row_north - row_east * col_north
                if abs(grid_determinant) <= 1e-15:
                    classification[local_row, local_col] = 0
                    coverage[local_row, local_col] = False
                    continue
                col_per_m = (
                    direction_x * row_north - row_east * direction_y
                ) / grid_determinant
                row_per_m = (
                    col_east * direction_y - col_north * direction_x
                ) / grid_determinant
                direction_x = a * col_per_m + b * row_per_m
                direction_y = d * col_per_m + e * row_per_m
                center_col = col + 0.5
                center_row = row + 0.5
                x0 = a * center_col + b * center_row + c
                y0 = d * center_col + e * center_row + f
                result_code = 1
                result_status = RAY_STATUS_SEARCH_LIMIT_REACHED
                for step in range(1, max_steps + 1):
                    distance_m = step * step_size_m
                    x = x0 + distance_m * direction_x
                    y = y0 + distance_m * direction_y
                    col_idx = (e * (x - c) - b * (y - f)) * inverse_det
                    row_idx = (-d * (x - c) + a * (y - f)) * inverse_det
                    terrain_row = int(math.floor(row_idx))
                    terrain_col = int(math.floor(col_idx))
                    if (terrain_row < 0 or terrain_row >= elevations.shape[0]
                            or terrain_col < 0 or terrain_col >= elevations.shape[1]):
                        result_code = 4
                        result_status = RAY_STATUS_DEM_BOUNDARY
                        break
                    terrain_elevation = elevations[terrain_row, terrain_col]
                    if not math.isfinite(terrain_elevation):
                        result_code = 4
                        result_status = RAY_STATUS_TERRAIN_NODATA
                        break
                    if terrain_elevation > elevation + obstruction_threshold_m:
                        result_code = 2
                        result_status = RAY_STATUS_OBSTRUCTION_FOUND
                        break
                classification[local_row, local_col] = result_code
                ray_status[local_row, local_col] = result_status
                if result_code == 4:
                    coverage[local_row, local_col] = False

        return classification, normal_valid, coverage, ray_status
