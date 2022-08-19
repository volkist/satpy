#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Satpy developers
#
# satpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# satpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with satpy.  If not, see <http://www.gnu.org/licenses/>.
"""The atms_l1b_nc reader tests package.
"""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest
import xarray as xr

from satpy.readers.atms_l1b_nc import AtmsL1bNCFileHandler


@pytest.fixture
def reader(l1b_file):
    """Return reader of ATMS level1b data."""
    return AtmsL1bNCFileHandler(
        filename=l1b_file,
        filename_info={"creation_time": datetime(2020, 1, 2, 3, 4, 5)},
        filetype_info={"antenna_temperature": "antenna_temp"},
    )


@pytest.fixture
def l1b_file(tmp_path, atms_fake_dataset):
    """Return file path to level1b file."""
    l1b_file_path = tmp_path / "test_file_atms_l1b.nc"
    atms_fake_dataset.to_netcdf(l1b_file_path)
    yield l1b_file_path


@pytest.fixture
def atms_fake_dataset():
    """Return fake ATMS dataset."""
    atrack = 2
    xtrack = 3
    channel = 22
    lon = np.full((atrack, xtrack), 1.)
    lat = np.full((atrack, xtrack), 2.)
    sat_azi = np.full((atrack, xtrack), 3.)
    antenna_temp = np.zeros((atrack, xtrack, channel))
    for idx in range(channel):
        antenna_temp[:, :, idx] = 100 + float(idx)
    return xr.Dataset(
        data_vars={
            "antenna_temp": (("atrack", "xtrack", "channel"), antenna_temp),
            "lon": (("atrack", "xtrack"), lon),
            "lat": (("atrack", "xtrack"), lat),
            "sat_azi": (("atrack", "xtrack"), sat_azi),
        },
        attrs={
            "time_coverage_start": "2000-01-02T03:04:05Z",
            "time_coverage_end": "2000-01-02T04:05:06Z",
            "platform": "JPSS-1",
            "instrument": "ATMS",
        },
    )


class TestAtsmsL1bNCFileHandler:
    """Test the AtmsL1bNCFileHandler reader."""

    def test_start_time(self, reader):
        """Test start time."""
        assert reader.start_time == datetime(2000, 1, 2, 3, 4, 5)
    
    def test_end_time(self, reader):
        """Test end time."""
        assert reader.end_time == datetime(2000, 1, 2, 4, 5, 6)

    def test_sensor(self, reader):
        """Test sensor."""
        assert reader.sensor == "ATMS"

    def test_platform_name(self, reader):
        """Test platform name."""
        assert reader.platform_name == "JPSS-1"

    def test_antenna_temperature(self, reader, atms_fake_dataset):
        """Test antenna temperature."""
        np.testing.assert_array_equal(
            reader.antenna_temperature,
            atms_fake_dataset.antenna_temp.values,
        )

    @pytest.mark.parametrize("param,expect", (
        ("start_time", datetime(2000, 1, 2, 3, 4, 5)),
        ("end_time", datetime(2000, 1, 2, 4, 5, 6)),
        ("platform_name", "JPSS-1"),
        ("sensor", "ATMS"),
    ))
    def test_attrs(self, reader, param, expect):
        """Test attributes."""
        assert reader.attrs[param] == expect

    @pytest.mark.parametrize("dims", (
        ("xtrack", "atrack"),
        ("x", "y"),
    ))
    def test_standardize_dims(self, reader, dims):
        """Test standardize dims."""
        variable = xr.DataArray(
            np.arange(6).reshape(2, 3),
            dims=dims,
        )
        standardized = reader._standardize_dims(variable)
        assert standardized.dims == ("y", "x")

    def test_drop_coords(self, reader):
        """Test drop coordinates."""
        coords = "dummy"
        data = xr.DataArray(
            np.ones(10),
            dims=("y"),
            coords={coords: 0},
        )
        assert coords in data.coords
        data = reader._drop_coords(data)
        assert coords not in data.coords

    @pytest.mark.parametrize("channel_name,expect", (
        ("1", 100.),
        ("2", 101.),
        ("22", 121.)
    ))
    def test_get_channel_data(self, reader, channel_name, expect):
        """Test get channel data."""
        np.testing.assert_array_equal(
            reader._get_channel_data(channel_name),
            np.full((2, 3), expect),
        )

    @pytest.mark.parametrize("param,expect", (
        ("start_time", datetime(2000, 1, 2, 3, 4, 5)),
        ("end_time", datetime(2000, 1, 2, 4, 5, 6)),
        ("platform_name", "JPSS-1"),
        ("sensor", "ATMS"),
        ("creation_time", datetime(2020, 1, 2, 3, 4, 5)),
        ("type", "test_data"),
        ("name", "test"),
    ))
    def test_merge_attributes(self, reader, param, expect):
        """Test merge attributes."""
        variable = data = xr.DataArray(
            np.ones(10),
            dims=("y"),
            attrs={"type": "test_data"},
        )
        dataset_info = {"name": "test"}
        variable = reader._merge_attributes(variable, dataset_info)
        assert variable.attrs[param] == expect

    def test_get_dataset_return_none_if_data_not_exist(self, reader):
        """Test get dataset return none if data does not exist."""
        dataset_id = {"name": "non_existing_data"}
        dataset_info = None
        dataset = reader.get_dataset(dataset_id, dataset_info)
        assert dataset is None

    @pytest.mark.parametrize("dataset_id,expect", (
        ({"name": "1"}, 100.),
        ({"name": "sat_azi"}, 3.),
    ))
    def test_get_dataset(self, reader, dataset_id, expect):
        """Tes get dataset handles channel data."""
        dataset = reader.get_dataset(dataset_id, {})
        np.testing.assert_array_equal(
            dataset,
            np.full((2, 3), expect),
        )
        assert dataset.dims == ("y", "x")
        assert dataset.attrs["sensor"] == "ATMS"
