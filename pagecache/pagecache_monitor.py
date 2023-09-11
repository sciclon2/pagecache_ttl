#!/usr/bin/env python3

import logging
import os
import time
from time import sleep

from datadog import initialize, statsd

import cache
from pagecache.exceptions import TmpDirDoesNotExist

logger = logging.getLogger(__name__)


class PageCacheMonitor(object):
    def __init__(
        self,
        tmp_directory,
        interval_seconds,
        max_time_window_seconds,
        logfile,
        send_metrics_to_dogstatsd=False,
    ):
        self.interval_seconds = interval_seconds
        self.max_time_window_seconds = max_time_window_seconds
        self.tmp_directory = tmp_directory
        self.send_metrics_to_dogstatsd = send_metrics_to_dogstatsd

        if not os.path.isdir(self.tmp_directory):
            logger.error("Tmp directory does not exist!")
            raise TmpDirDoesNotExist()

        if send_metrics_to_dogstatsd:
            self.dogstatsd_options = {"statsd_host": "127.0.0.1", "statsd_port": 8125}
            initialize(**self.dogstatsd_options)
            self.dogstatsd_metric_name = "pagecache_ttl.min_cached_time_seconds"
            self.statsd = statsd

    def _create_new_file(self):
        """
        Create a new file with dummy content, the content
        will satisfy only one page, so it's smaller than page_size 4k
        Filename is the current timestamp to avoid extra system calls to stat the files
        """

        filename = str(int(time.time()))  # Current TimeStamp
        fd = open("{}/{}".format(self.tmp_directory, filename), "w")
        fd.write(filename)  # dummy write
        # Force write to disk https://docs.python.org/3/library/os.html#os.fsync
        fd.flush()
        os.fsync(fd)
        logger.debug("Created file {}".format(filename))

    def _delete_files(self, existing_files, index_to_start_deletion):
        """
        Deletes the files on the existing_files list starting for the index index_to_start_deletion until the end.
        Example:
            existing_files =  [1693739406, 1693739405, 1693739404, 1693739403, 1693739402]
            index_to_start_deletion = 2
            deleted files will be = 1693739404, 1693739403 and 1693739402
        """
        logger.debug(
            "Total files {} in list, deleting files starting from list index {} until the end of the list ".format(
                len(existing_files), index_to_start_deletion
            )
        )
        for file_to_delete in existing_files[index_to_start_deletion:]:
            os.remove("{}/{}".format(self.tmp_directory, file_to_delete))
            logger.debug("Deleted file {}".format(file_to_delete))

    def _get_first_expired_file(self, existing_files, now):
        """
        Searches for the first ocurrence of an expired file in the existing_files and returns a touple
        with the index and the filename
        If there is not any expired file in the list we return -1
        """
        # Find the first file in the list older than self.max_time_window_seconds
        for idx, file in enumerate(existing_files):
            if int(file) < now - self.max_time_window_seconds:
                logger.debug(
                    "First expired file in list: {}, list index location: {}".format(
                        file, idx
                    )
                )
                return (idx, file)
        # All files are within self.max_time_window_seconds or there are not files, return a negative index
        logger.debug(
            "Can't get first expired file ocurrence in the list, either all files are within the max_time_window_seconds or empty list"
        )
        return (-1, None)

    def _get_first_not_cached_file(self, existing_files):
        """
        Searches for the first ocurrence of a non-cached file in the existing_files and returns a touple
        with the index and the filename
        If all the existing files are cached in the list then we return -1
        """
        for idx, file in enumerate(existing_files):
            with open("{}/{}".format(self.tmp_directory, file), "r") as fd:
                page_cache_status = cache.ratio(fd.fileno())
                if (
                    page_cache_status[0] == 0
                ):  # First not cached file in the list, so the previous one was the last cached
                    logger.debug(
                        "First not cached file in list: {}, list index location: {}".format(
                            file, idx
                        )
                    )
                    return (idx, int(file))
        # All files are cached or there are not files, return a negative index
        logger.debug(
            "Can't get first not cached file ocurrence in the list, either all files are cached or empty list"
        )
        return (-1, None)

    def _get_existing_files(self):
        """
        Returns a list of filenames sorted and reverse
        Example : [1693739406, 1693739405, 1693739404]
        """
        existing_files = [int(file) for file in os.listdir(self.tmp_directory)]
        existing_files.sort()
        existing_files.reverse()
        logger.debug("Sorted existing files: {}".format(existing_files))
        return existing_files

    def _balance_files(self, idx_to_start_deletion, existing_files):
        """
        Balances the removal and creation of files,
        """
        # Delete old expired or not cached files
        self._delete_files(existing_files, idx_to_start_deletion)

        # Create new file
        self._create_new_file()

    def _get_index_to_start_deletion(self, existing_files, now):
        """
        Gets the smallest index which matches the condition to start a deletion from that point onwards.
        Example:
            existing_files =  [1693739406, 1693739405, 1693739404, 1693739403, 1693739402]
            idx_first_not_cached_file = 2
            idx_first_expired_file = 3
        This will return 2 as we need to get rid of all the files onwards.
        """
        idx_first_expired_file, name_first_expired_file = self._get_first_expired_file(
            existing_files, now
        )
        (
            idx_first_not_cached_file,
            name_first_not_cached_file,
        ) = self._get_first_not_cached_file(existing_files)

        # If we have both cached and expired we chose the youngest one to start the deletion from that point
        if idx_first_expired_file != -1 and idx_first_not_cached_file != -1:
            idx_to_start_deletion = min(
                [idx_first_expired_file, idx_first_not_cached_file]
            )
            logger.debug(
                "Found in file list both expired and uncached files to delete, chosing the first ocurrence in the list to start deletion which is the index: {}".format(
                    idx_to_start_deletion
                )
            )
        # If there is not files to delete return -1
        elif idx_first_expired_file == -1 and idx_first_not_cached_file == -1:
            idx_to_start_deletion = -1
            logger.debug("Not found files for deletion from the existing list.")
        # If only one condition of deletion is met we return that index
        else:
            if idx_first_expired_file == -1:
                idx_to_start_deletion = int(idx_first_not_cached_file)
                logger.debug(
                    "Found in file list of uncached files for deletion, getting the index {} of the list to start deletion ".format(
                        idx_to_start_deletion
                    )
                )
            else:
                idx_to_start_deletion = int(idx_first_expired_file)
                logger.debug(
                    "Found in file list of expired files for deletion, getting the index {} of the list to start deletion ".format(
                        idx_to_start_deletion
                    )
                )

        return idx_to_start_deletion

    def _deliver_metrics_to_dogstatsd(self, min_cached_time):
        """
        Sends metrics to DogStatsD (localhost)
        """
        self.statsd.gauge(self.dogstatsd_metric_name, min_cached_time)
        logger.debug(
            "Delivered metric to DogStatsD: {}:{}".format(
                self.dogstatsd_metric_name, min_cached_time
            )
        )

    def _report_metric(self, min_cached_time):
        if self.send_metrics_to_dogstatsd:
            self._deliver_metrics_to_dogstatsd(min_cached_time)
        else:
            print({"min_cached_time": min_cached_time})
        logger.info(
            "Current min time page is cached: {} seconds".format(min_cached_time)
        )

    def run(self):
        """
        Main loop which will live until the process gets a Signal
        """
        while True:
            self._create_new_file()
            existing_files = self._get_existing_files()
            now = int(time.time())  # Current TimeStamp

            index_to_start_deletion = self._get_index_to_start_deletion(
                existing_files, now
            )
            if index_to_start_deletion >= 0:
                self._delete_files(existing_files, index_to_start_deletion)
                min_cached_time = now - existing_files[index_to_start_deletion - 1]
            else:
                min_cached_time = now - existing_files[-1]
            self._report_metric(min_cached_time)
            sleep(self.interval_seconds)
