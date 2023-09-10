import argparse
import logging

import daemon
from pid import PidFile

from pagecache.configure_logging import configure_logging
from pagecache.pagecache_monitor import PageCacheMonitor

logger = logging.getLogger(__name__)


def parseargs():
    parser = argparse.ArgumentParser(description="PageCache TTL")
    parser.add_argument(
        "--tmp-dir",
        type=str,
        default="tmp/",
        help="Sets the tmp directory wher ehte program stores the tracking dummy files.",
        required=False,
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=5,
        help="Sets the interval to check oldest cached sample (in seconds)",
        required=False,
    )
    parser.add_argument(
        "--max-time-window-seconds",
        type=int,
        default=3600,
        help="Sets the maximum time to check keep track of page cache (in seconds)",
        required=False,
    )
    parser.add_argument(
        "--daemon",
        required=False,
        default=False,
        action="store_true",
        help="Execute the program in daemon mode.",
    )
    parser.add_argument(
        "--send-metrics-to-dogstatsd",
        required=False,
        default=False,
        action="store_true",
        help="Send metrics to local DogStatsD https://docs.datadoghq.com/developers/dogstatsd/",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["INFO", "WARNING", "DEBUG"],
        default="INFO",
        help="Sets the debug level",
        required=False,
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="/var/log/pagecache_ttl.log",
        help="Sets the tmp directory wher ehte program stores the tracking dummy files.",
        required=False,
    )
    return parser.parse_args()


def load_daemon_mode(args, log_file, log_file_fd):
    context = daemon.DaemonContext(
        working_directory="/opt/pagecache_ttl",
        umask=0o002,
        pidfile=PidFile(pidname=log_file),
    )
    context.files_preserve = [log_file_fd]

    with context:
        pagecache_monitor = PageCacheMonitor(
            args.tmp_dir,
            args.interval_seconds,
            args.max_time_window_seconds,
            args.send_metrics_to_dogstatsd,
        )
        pagecache_monitor.run()


def load_script_mode(args):
    pagecache_monitor = PageCacheMonitor(
        args.tmp_dir,
        args.interval_seconds,
        args.max_time_window_seconds,
        args.send_metrics_to_dogstatsd,
    )
    pagecache_monitor.run()


def main():
    args = parseargs()
    log_file_fd = configure_logging(args.log_level, args.log_file)

    if args.daemon:
        logger.info("Starting PageCache TTL service as daemon mode...")
        load_daemon_mode(args, args.log_file, log_file_fd)
    else:
        logger.info("Starting PageCache TTL as script mode...")
        load_script_mode(args)
