# import pytest

import io
import sys
import time
from pathlib import Path
from unittest.mock import Mock, call, patch

from datadog import statsd
from mock_open import MockOpen

import cache
from pagecache.pagecache_monitor import PageCacheMonitor

EXISTING_FILES = [
    1693739406,
    1693739405,
    1693739404,
    1693739403,
    1693739402,
    1693739349,
    1693739348,
]


def test_create_new_file(tmp_path):
    # Setting up mocked filename
    filename = "123456789"

    # Create mocked tmp dir
    pagecache_tmp_dir = tmp_path / "pagecache/"
    pagecache_tmp_dir.mkdir()

    # Create object and test _create_new_file()
    pcm = PageCacheMonitor(pagecache_tmp_dir, 1, 5, "var/log/pagecache.log")
    with patch.object(time, "time", return_value=filename):
        pcm._create_new_file()

    # Check if file exists and has the expected content
    created_file = "{}/{}".format(pagecache_tmp_dir, filename)
    with open(created_file, "r") as fd:
        assert fd.read() == filename


def test_delete_files(tmp_path):
    # Create mocked tmp dir
    pagecache_tmp_dir = tmp_path / "pagecache/"
    pagecache_tmp_dir.mkdir()

    # Create files
    [
        Path("{}/{}".format(pagecache_tmp_dir, str(file))).touch()
        for file in EXISTING_FILES
    ]

    # Create object and test _delete_files(), Delete started from the index 2 (included)
    index_to_start_deletion = 2
    pcm = PageCacheMonitor(pagecache_tmp_dir, 1, 5, "var/log/pagecache.log")
    pcm._delete_files(EXISTING_FILES, index_to_start_deletion)

    # Check the existing files after deletion
    assert pcm._get_existing_files() == EXISTING_FILES[:index_to_start_deletion]


def test_get_first_expired_file():
    max_time_window_seconds = 60
    current_ts = 1693739410

    # 1693739349, 1693739348 already expired
    pcm = PageCacheMonitor("/tmp", 1, max_time_window_seconds, "var/log/pagecache.log")
    first_expired_file = pcm._get_first_expired_file(EXISTING_FILES, current_ts)

    # First expired in position 5  (1693739410 - 60 = 1693739350)
    assert first_expired_file == (5, 1693739349)

    # Not expired file
    max_time_window_seconds = 120
    pcm = PageCacheMonitor("/tmp", 1, max_time_window_seconds, "var/log/pagecache.log")
    first_expired_file = pcm._get_first_expired_file(EXISTING_FILES, current_ts)
    assert first_expired_file == (-1, None)


def test_get_first_not_cached_file():
    first_not_cached_file = 1693739403
    # If 1693739403 is not cached it must be deleted adn all the next iems on the list
    pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")

    # First not cached file is at index 3
    with patch.object(
        cache, "ratio", side_effect=[(1, 1), (1, 1), (1, 1), (0, 0)]
    ), patch("builtins.open", MockOpen()):
        # First not cached file is at index 3
        assert pcm._get_first_not_cached_file(EXISTING_FILES) == (
            3,
            first_not_cached_file,
        )

    # non-cached file not found
    with patch.object(
        cache,
        "ratio",
        side_effect=[(1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1)],
    ), patch("builtins.open", MockOpen()):
        assert pcm._get_first_not_cached_file(EXISTING_FILES) == (-1, None)


def test_get_existing_files(tmp_path):
    # Create mocked tmp dir
    pagecache_tmp_dir = tmp_path / "pagecache/"
    pagecache_tmp_dir.mkdir()

    # Create files
    [
        Path("{}/{}".format(pagecache_tmp_dir, str(file))).touch()
        for file in EXISTING_FILES
    ]

    pcm = PageCacheMonitor(pagecache_tmp_dir, 1, 120, "var/log/pagecache.log")
    assert pcm._get_existing_files() == EXISTING_FILES


def test_balance_files():
    idx_to_start_deletion = 2

    with patch.object(
        PageCacheMonitor, "_delete_files"
    ) as mock_delete_files, patch.object(
        PageCacheMonitor, "_create_new_file"
    ) as mock_create_new_file:
        mock_called_methods = Mock()

        mock_called_methods.attach_mock(mock_delete_files, "_delete_files")
        mock_called_methods.attach_mock(mock_create_new_file, "_create_new_file")

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        pcm._balance_files(idx_to_start_deletion, EXISTING_FILES)

        # Make sure _delete_files() and _create_new_file are called in a sorted mode
        mock_called_methods.assert_has_calls(
            [
                call._delete_files(EXISTING_FILES, idx_to_start_deletion),
                call._create_new_file(),
            ],
            any_order=False,
        )


def test_get_index_to_start_deletion():
    current_ts = 1693739410

    with patch.object(
        PageCacheMonitor, "_get_first_expired_file"
    ) as mock_get_first_expired_file, patch.object(
        PageCacheMonitor, "_get_first_not_cached_file"
    ) as mock_get_first_not_cached_file:
        # First text first_expired_file is the smallest idx
        first_expired_file = (2, 1693739404)
        first_not_cached_file = (3, 1693739403)
        mock_get_first_expired_file.return_value = first_expired_file
        mock_get_first_not_cached_file.return_value = first_not_cached_file

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        index_to_start_deletion = pcm._get_index_to_start_deletion(
            EXISTING_FILES, current_ts
        )

        assert index_to_start_deletion == first_expired_file[0]

        # Second text first_not_cached_file is the smallest idx
        first_expired_file = (3, 1693739403)
        first_not_cached_file = (1, 1693739405)
        mock_get_first_expired_file.return_value = first_expired_file
        mock_get_first_not_cached_file.return_value = first_not_cached_file

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        index_to_start_deletion = pcm._get_index_to_start_deletion(
            EXISTING_FILES, current_ts
        )

        assert index_to_start_deletion == first_not_cached_file[0]

        # Third text first_not_cached_file not found
        first_expired_file = (3, 1693739403)
        first_not_cached_file = (-1, None)
        mock_get_first_expired_file.return_value = first_expired_file
        mock_get_first_not_cached_file.return_value = first_not_cached_file

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        index_to_start_deletion = pcm._get_index_to_start_deletion(
            EXISTING_FILES, current_ts
        )

        assert index_to_start_deletion == first_expired_file[0]

        # Fourth text first_expired_file not found
        first_expired_file = (-1, None)
        first_not_cached_file = (3, 1693739403)
        mock_get_first_expired_file.return_value = first_expired_file
        mock_get_first_not_cached_file.return_value = first_not_cached_file

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        index_to_start_deletion = pcm._get_index_to_start_deletion(
            EXISTING_FILES, current_ts
        )

        assert index_to_start_deletion == first_not_cached_file[0]

        # Fifth text first_expired_file and first_not_cached_file not found
        first_expired_file = (-1, None)
        first_not_cached_file = (-1, None)
        mock_get_first_expired_file.return_value = first_expired_file
        mock_get_first_not_cached_file.return_value = first_not_cached_file

        pcm = PageCacheMonitor("/tmp", 1, 120, "var/log/pagecache.log")
        index_to_start_deletion = pcm._get_index_to_start_deletion(
            EXISTING_FILES, current_ts
        )

        assert index_to_start_deletion == -1


def test_deliver_metrics_to_dogstatsd():
    min_cached_time = 15
    pcm = PageCacheMonitor(
        "/tmp", 1, 120, "var/log/pagecache.log", send_metrics_to_dogstatsd=True
    )

    with patch.object(statsd, "gauge") as mock_statsd_gauge:
        pcm._deliver_metrics_to_dogstatsd(min_cached_time)

    # Check the method was called with the proper argument of min_cached_time
    mock_statsd_gauge.assert_called_once_with(
        pcm.dogstatsd_metric_name, min_cached_time
    )


def test_report_metric():
    # First test send_metrics_to_dogstatsd=True
    min_cached_time = 15

    pcm = PageCacheMonitor(
        "/tmp", 1, 120, "var/log/pagecache.log", send_metrics_to_dogstatsd=True
    )

    with patch.object(
        PageCacheMonitor, "_deliver_metrics_to_dogstatsd"
    ) as mock_deliver_metrics_to_dogstatsd:
        pcm._report_metric(min_cached_time)

    mock_deliver_metrics_to_dogstatsd.assert_called_once_with(min_cached_time)

    # Second test only prints to STDOUT
    pcm = PageCacheMonitor(
        "/tmp", 1, 120, "var/log/pagecache.log", send_metrics_to_dogstatsd=False
    )
    with patch.object(
        PageCacheMonitor, "_deliver_metrics_to_dogstatsd"
    ) as mock_deliver_metrics_to_dogstatsd:
        pcm._report_metric(min_cached_time)

        captured_stdout = io.StringIO()
        sys.stdout = captured_stdout
        pcm._report_metric(min_cached_time)
        sys.stdout = sys.__stdout__
        assert captured_stdout.getvalue().strip() == "{{'{}': {}}}".format(
            "min_cached_time", min_cached_time
        )
