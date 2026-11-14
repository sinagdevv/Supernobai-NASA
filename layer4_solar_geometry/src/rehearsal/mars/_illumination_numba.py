"""Mars-specific parallel kernels for radial-surface illumination."""

from __future__ import annotations

import math

import numpy as np

RAY_NO_DATA = -1
RAY_UNKNOWN = 0
RAY_SEARCH_LIMIT = 1
RAY_OBSTRUCTION = 2
RAY_DEM_BOUNDARY = 3
RAY_TERRAIN_NODATA = 4
RAY_OBSERVATION_GAP = 5
RAY_NORMAL_BOUNDARY = 6
RAY_NORMAL_NODATA = 7
RAY_SURFACE_AWAY = 8
RAY_VERTICAL_SUN = 9
RAY_GRID_DEGENERATE = 10
RAY_STEP_LIMIT = 11
RAY_OK = 12

try:
    from numba import get_num_threads, njit, prange
except ImportError:  # pragma: no cover - depends on the optional performance extra
    get_num_threads = None
    njit = None
    prange = None


def is_available() -> bool:
    return njit is not None


def thread_count() -> int | None:
    return None if get_num_threads is None else int(get_num_threads())


if njit is not None:

    @njit(cache=True, parallel=True)
    def surface_positions(radial_distance_m, longitude_deg, latitude_deg, valid):
        height, width = radial_distance_m.shape
        positions = np.zeros((height, width, 3), dtype=np.float64)
        for row in prange(height):
            for col in range(width):
                if not valid[row, col]:
                    continue
                lon = longitude_deg[row, col] * (math.pi / 180.0)
                lat = latitude_deg[row, col] * (math.pi / 180.0)
                radius = radial_distance_m[row, col]
                cos_lat = math.cos(lat)
                positions[row, col, 0] = radius * cos_lat * math.cos(lon)
                positions[row, col, 1] = radius * cos_lat * math.sin(lon)
                positions[row, col, 2] = radius * math.sin(lat)
        return positions

    @njit(cache=True)
    def _basis(longitude_rad, x, y, z, radius_a, radius_b, radius_c):
        up_x = x / (radius_a * radius_a)
        up_y = y / (radius_b * radius_b)
        up_z = z / (radius_c * radius_c)
        up_norm = math.sqrt(up_x * up_x + up_y * up_y + up_z * up_z)
        if not math.isfinite(up_norm) or up_norm <= 0.0:
            return (0.0,) * 9 + (False,)
        up_x /= up_norm
        up_y /= up_norm
        up_z /= up_norm

        east_x = -math.sin(longitude_rad)
        east_y = math.cos(longitude_rad)
        east_z = 0.0
        projection = east_x * up_x + east_y * up_y
        east_x -= projection * up_x
        east_y -= projection * up_y
        east_z -= projection * up_z
        east_norm = math.sqrt(east_x * east_x + east_y * east_y + east_z * east_z)
        if not math.isfinite(east_norm) or east_norm <= 1e-12:
            return (0.0,) * 9 + (False,)
        east_x /= east_norm
        east_y /= east_norm
        east_z /= east_norm

        north_x = up_y * east_z - up_z * east_y
        north_y = up_z * east_x - up_x * east_z
        north_z = up_x * east_y - up_y * east_x
        north_norm = math.sqrt(north_x * north_x + north_y * north_y + north_z * north_z)
        if not math.isfinite(north_norm) or north_norm <= 1e-12:
            return (0.0,) * 9 + (False,)
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
    def _cell_check(
        positions,
        surface_valid,
        observation_coverage,
        row,
        col,
        distance_m,
        center_x,
        center_y,
        center_z,
        up_x,
        up_y,
        up_z,
        ray_dir_x,
        ray_dir_y,
        ray_dir_z,
        ray_slope,
        obstruction_tolerance_m,
    ):
        row = int(row)
        col = int(col)
        height, width = surface_valid.shape
        if row < 0 or row >= height or col < 0 or col >= width:
            return RAY_DEM_BOUNDARY, False
        if not surface_valid[row, col]:
            return RAY_TERRAIN_NODATA, False
        if not observation_coverage[row, col]:
            return RAY_OBSERVATION_GAP, False

        delta_x = positions[row, col, 0] - center_x
        delta_y = positions[row, col, 1] - center_y
        delta_z = positions[row, col, 2] - center_z
        relative_height = delta_x * up_x + delta_y * up_y + delta_z * up_z
        along_ray = delta_x * ray_dir_x + delta_y * ray_dir_y + delta_z * ray_dir_z
        if along_ray <= 0.0:
            along_ray = distance_m
        ray_height = along_ray * ray_slope
        return RAY_OK, relative_height > ray_height + obstruction_tolerance_m

    @njit(cache=True)
    def _trace_ray(
        positions,
        surface_valid,
        observation_coverage,
        row,
        col,
        sun_east,
        sun_north,
        sun_up,
        east_x,
        east_y,
        east_z,
        north_x,
        north_y,
        north_z,
        up_x,
        up_y,
        up_z,
        max_distance_m,
        obstruction_tolerance_m,
    ):
        row = int(row)
        col = int(col)
        height, width = surface_valid.shape
        if (
            row <= 0
            or col <= 0
            or row >= height - 1
            or col >= width - 1
        ):
            return RAY_NORMAL_BOUNDARY

        west_x = positions[row, col - 1, 0]
        west_y = positions[row, col - 1, 1]
        west_z = positions[row, col - 1, 2]
        east2_x = positions[row, col + 1, 0]
        east2_y = positions[row, col + 1, 1]
        east2_z = positions[row, col + 1, 2]
        north2_x = positions[row - 1, col, 0]
        north2_y = positions[row - 1, col, 1]
        north2_z = positions[row - 1, col, 2]
        south_x = positions[row + 1, col, 0]
        south_y = positions[row + 1, col, 1]
        south_z = positions[row + 1, col, 2]

        col_delta_x = 0.5 * (east2_x - west_x)
        col_delta_y = 0.5 * (east2_y - west_y)
        col_delta_z = 0.5 * (east2_z - west_z)
        row_delta_x = 0.5 * (south_x - north2_x)
        row_delta_y = 0.5 * (south_y - north2_y)
        row_delta_z = 0.5 * (south_z - north2_z)
        col_east = col_delta_x * east_x + col_delta_y * east_y + col_delta_z * east_z
        col_north = col_delta_x * north_x + col_delta_y * north_y + col_delta_z * north_z
        row_east = row_delta_x * east_x + row_delta_y * east_y + row_delta_z * east_z
        row_north = row_delta_x * north_x + row_delta_y * north_y + row_delta_z * north_z
        determinant = col_east * row_north - row_east * col_north
        if not math.isfinite(determinant) or abs(determinant) <= 1e-12:
            return RAY_GRID_DEGENERATE

        horizontal_norm = math.sqrt(sun_east * sun_east + sun_north * sun_north)
        east_component = sun_east / horizontal_norm
        north_component = sun_north / horizontal_norm
        col_per_m = (east_component * row_north - row_east * north_component) / determinant
        row_per_m = (col_east * north_component - col_north * east_component) / determinant
        col_rate = abs(col_per_m)
        row_rate = abs(row_per_m)
        if col_rate <= 1e-15 and row_rate <= 1e-15:
            return RAY_VERTICAL_SUN
        col_step = 1 if col_per_m > 0.0 else -1
        row_step = 1 if row_per_m > 0.0 else -1
        col_delta = math.inf if col_rate <= 1e-15 else 1.0 / col_rate
        row_delta = math.inf if row_rate <= 1e-15 else 1.0 / row_rate
        col_next = math.inf if col_rate <= 1e-15 else 0.5 / col_rate
        row_next = math.inf if row_rate <= 1e-15 else 0.5 / row_rate
        current_row = row
        current_col = col
        center_x = positions[row, col, 0]
        center_y = positions[row, col, 1]
        center_z = positions[row, col, 2]
        east_dir_x = east_component * east_x
        east_dir_y = east_component * east_y
        east_dir_z = east_component * east_z
        north_dir_x = north_component * north_x
        north_dir_y = north_component * north_y
        north_dir_z = north_component * north_z
        ray_dir_x = east_dir_x + north_dir_x
        ray_dir_y = east_dir_y + north_dir_y
        ray_dir_z = east_dir_z + north_dir_z
        ray_slope = sun_up / horizontal_norm

        for _ in range((height + width) * 2 + 8):
            next_distance = min(col_next, row_next)
            if next_distance > max_distance_m:
                return RAY_SEARCH_LIMIT
            tie = abs(col_next - row_next) <= 1e-10 * max(1.0, next_distance)
            if tie:
                check_col = current_col + col_step
                check_row = current_row + row_step
                status_col, blocked_col = _cell_check(
                    positions, surface_valid, observation_coverage,
                    current_row, check_col, next_distance,
                    center_x, center_y, center_z, up_x, up_y, up_z,
                    ray_dir_x, ray_dir_y, ray_dir_z, ray_slope,
                    obstruction_tolerance_m,
                )
                status_row, blocked_row = _cell_check(
                    positions, surface_valid, observation_coverage,
                    check_row, current_col, next_distance,
                    center_x, center_y, center_z, up_x, up_y, up_z,
                    ray_dir_x, ray_dir_y, ray_dir_z, ray_slope,
                    obstruction_tolerance_m,
                )
                status_diagonal, blocked_diagonal = _cell_check(
                    positions, surface_valid, observation_coverage,
                    check_row, check_col, next_distance,
                    center_x, center_y, center_z, up_x, up_y, up_z,
                    ray_dir_x, ray_dir_y, ray_dir_z, ray_slope,
                    obstruction_tolerance_m,
                )
                if (
                    status_col != RAY_OK
                    or status_row != RAY_OK
                    or status_diagonal != RAY_OK
                ):
                    if (
                        status_col == RAY_OBSERVATION_GAP
                        or status_row == RAY_OBSERVATION_GAP
                        or status_diagonal == RAY_OBSERVATION_GAP
                    ):
                        return RAY_OBSERVATION_GAP
                    if (
                        status_col == RAY_TERRAIN_NODATA
                        or status_row == RAY_TERRAIN_NODATA
                        or status_diagonal == RAY_TERRAIN_NODATA
                    ):
                        return RAY_TERRAIN_NODATA
                    return RAY_DEM_BOUNDARY
                if blocked_col or blocked_row or blocked_diagonal:
                    return RAY_OBSTRUCTION
                current_row = check_row
                current_col = check_col
                col_next += col_delta
                row_next += row_delta
            elif col_next < row_next:
                current_col += col_step
                status, blocked = _cell_check(
                    positions, surface_valid, observation_coverage,
                    current_row, current_col, next_distance,
                    center_x, center_y, center_z, up_x, up_y, up_z,
                    ray_dir_x, ray_dir_y, ray_dir_z, ray_slope,
                    obstruction_tolerance_m,
                )
                if status != RAY_OK:
                    return status
                if blocked:
                    return RAY_OBSTRUCTION
                col_next += col_delta
            else:
                current_row += row_step
                status, blocked = _cell_check(
                    positions, surface_valid, observation_coverage,
                    current_row, current_col, next_distance,
                    center_x, center_y, center_z, up_x, up_y, up_z,
                    ray_dir_x, ray_dir_y, ray_dir_z, ray_slope,
                    obstruction_tolerance_m,
                )
                if status != RAY_OK:
                    return status
                if blocked:
                    return RAY_OBSTRUCTION
                row_next += row_delta
        return RAY_STEP_LIMIT

    @njit(cache=True, parallel=True)
    def classify_grid(
        positions,
        longitude_deg,
        surface_valid,
        observation_coverage,
        sun_position_m,
        radii_m,
        max_distance_m,
        dot_tolerance,
        obstruction_tolerance_m,
    ):
        height, width = surface_valid.shape
        classification = np.full((height, width), 0, dtype=np.int16)
        ray_status = np.full((height, width), RAY_UNKNOWN, dtype=np.int8)
        normal_valid = np.zeros((height, width), dtype=np.bool_)
        coverage = np.zeros((height, width), dtype=np.bool_)
        normals = np.full((height, width, 3), np.nan, dtype=np.float64)
        solar_elevation = np.full((height, width), np.nan, dtype=np.float64)
        solar_azimuth = np.full((height, width), np.nan, dtype=np.float64)
        solar_incidence = np.full((height, width), np.nan, dtype=np.float64)
        radius_a, radius_b, radius_c = radii_m
        radians_to_degrees = 180.0 / math.pi

        for row in prange(height):
            for col in range(width):
                if not surface_valid[row, col]:
                    classification[row, col] = -1
                    ray_status[row, col] = RAY_NO_DATA
                    continue

                x = positions[row, col, 0]
                y = positions[row, col, 1]
                z = positions[row, col, 2]
                longitude_rad = longitude_deg[row, col] * (math.pi / 180.0)
                (east_x, east_y, east_z,
                 north_x, north_y, north_z,
                 up_x, up_y, up_z, basis_valid) = _basis(
                    longitude_rad, x, y, z, radius_a, radius_b, radius_c
                )
                if not basis_valid:
                    classification[row, col] = 4
                    ray_status[row, col] = RAY_GRID_DEGENERATE
                    continue

                to_sun_x = sun_position_m[0] - x
                to_sun_y = sun_position_m[1] - y
                to_sun_z = sun_position_m[2] - z
                to_sun_norm = math.sqrt(
                    to_sun_x * to_sun_x
                    + to_sun_y * to_sun_y
                    + to_sun_z * to_sun_z
                )
                if not math.isfinite(to_sun_norm) or to_sun_norm <= 0.0:
                    classification[row, col] = 0
                    ray_status[row, col] = RAY_UNKNOWN
                    continue
                to_sun_x /= to_sun_norm
                to_sun_y /= to_sun_norm
                to_sun_z /= to_sun_norm
                sun_east = to_sun_x * east_x + to_sun_y * east_y + to_sun_z * east_z
                sun_north = (
                    to_sun_x * north_x + to_sun_y * north_y + to_sun_z * north_z
                )
                sun_up = to_sun_x * up_x + to_sun_y * up_y + to_sun_z * up_z
                horizontal = math.sqrt(sun_east * sun_east + sun_north * sun_north)
                solar_elevation[row, col] = math.atan2(sun_up, horizontal) * radians_to_degrees
                if horizontal > 1e-14:
                    azimuth = math.atan2(sun_east, sun_north) * radians_to_degrees
                    solar_azimuth[row, col] = azimuth % 360.0
                if not observation_coverage[row, col]:
                    classification[row, col] = 4
                    ray_status[row, col] = RAY_OBSERVATION_GAP
                    continue

                if (
                    row == 0
                    or col == 0
                    or row == height - 1
                    or col == width - 1
                ):
                    classification[row, col] = 4
                    ray_status[row, col] = RAY_NORMAL_BOUNDARY
                    continue
                neighbor_status = RAY_OK
                if not (
                    surface_valid[row, col - 1]
                    and surface_valid[row, col + 1]
                    and surface_valid[row - 1, col]
                    and surface_valid[row + 1, col]
                ):
                    neighbor_status = RAY_NORMAL_NODATA
                elif not (
                    observation_coverage[row, col - 1]
                    and observation_coverage[row, col + 1]
                    and observation_coverage[row - 1, col]
                    and observation_coverage[row + 1, col]
                ):
                    neighbor_status = RAY_OBSERVATION_GAP
                if neighbor_status != RAY_OK:
                    classification[row, col] = 4
                    ray_status[row, col] = neighbor_status
                    continue

                west_x = positions[row, col - 1, 0]
                west_y = positions[row, col - 1, 1]
                west_z = positions[row, col - 1, 2]
                east2_x = positions[row, col + 1, 0]
                east2_y = positions[row, col + 1, 1]
                east2_z = positions[row, col + 1, 2]
                north2_x = positions[row - 1, col, 0]
                north2_y = positions[row - 1, col, 1]
                north2_z = positions[row - 1, col, 2]
                south_x = positions[row + 1, col, 0]
                south_y = positions[row + 1, col, 1]
                south_z = positions[row + 1, col, 2]
                tangent_col_x = east2_x - west_x
                tangent_col_y = east2_y - west_y
                tangent_col_z = east2_z - west_z
                tangent_row_x = south_x - north2_x
                tangent_row_y = south_y - north2_y
                tangent_row_z = south_z - north2_z
                normal_x = tangent_col_y * tangent_row_z - tangent_col_z * tangent_row_y
                normal_y = tangent_col_z * tangent_row_x - tangent_col_x * tangent_row_z
                normal_z = tangent_col_x * tangent_row_y - tangent_col_y * tangent_row_x
                if normal_x * up_x + normal_y * up_y + normal_z * up_z < 0.0:
                    normal_x = -normal_x
                    normal_y = -normal_y
                    normal_z = -normal_z
                normal_norm = math.sqrt(
                    normal_x * normal_x + normal_y * normal_y + normal_z * normal_z
                )
                if not math.isfinite(normal_norm) or normal_norm <= 1e-12:
                    classification[row, col] = 4
                    ray_status[row, col] = RAY_GRID_DEGENERATE
                    continue
                normal_x /= normal_norm
                normal_y /= normal_norm
                normal_z /= normal_norm
                normals[row, col, 0] = normal_x
                normals[row, col, 1] = normal_y
                normals[row, col, 2] = normal_z
                normal_valid[row, col] = True

                incidence_dot = (
                    normal_x * to_sun_x
                    + normal_y * to_sun_y
                    + normal_z * to_sun_z
                )
                incidence_dot = min(1.0, max(-1.0, incidence_dot))
                solar_incidence[row, col] = math.acos(incidence_dot) * radians_to_degrees
                if incidence_dot <= dot_tolerance:
                    classification[row, col] = 3
                    ray_status[row, col] = RAY_SURFACE_AWAY
                    coverage[row, col] = True
                    continue
                if horizontal <= 1e-14:
                    classification[row, col] = 1
                    ray_status[row, col] = RAY_VERTICAL_SUN
                    coverage[row, col] = True
                    continue

                ray_code = _trace_ray(
                    positions,
                    surface_valid,
                    observation_coverage,
                    row,
                    col,
                    sun_east,
                    sun_north,
                    sun_up,
                    east_x,
                    east_y,
                    east_z,
                    north_x,
                    north_y,
                    north_z,
                    up_x,
                    up_y,
                    up_z,
                    max_distance_m,
                    obstruction_tolerance_m,
                )
                if ray_code == RAY_OBSTRUCTION:
                    classification[row, col] = 2
                    ray_status[row, col] = RAY_OBSTRUCTION
                    coverage[row, col] = True
                elif ray_code == RAY_SEARCH_LIMIT:
                    classification[row, col] = 1
                    ray_status[row, col] = RAY_SEARCH_LIMIT
                    coverage[row, col] = True
                else:
                    classification[row, col] = 4
                    ray_status[row, col] = ray_code
        return (
            classification,
            normal_valid,
            coverage,
            ray_status,
            normals,
            solar_elevation,
            solar_azimuth,
            solar_incidence,
        )

else:

    def surface_positions(*_args, **_kwargs):
        raise RuntimeError(
            "Numba is required for Mars terrain illumination; install the 'performance' extra"
        )

    def classify_grid(*_args, **_kwargs):
        raise RuntimeError(
            "Numba is required for Mars terrain illumination; install the 'performance' extra"
        )
