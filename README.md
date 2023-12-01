# pagecache_ttl
# Overview
Memory administration is a complex topic in which the Kernel OS maintains two LRU (Least Recently Used) lists, known as the inactive and active lists. These lists help in efficiently managing pages in memory, reducing the need for disk access.

When a page is accessed or created by a user-space program, it is initially added to the inactive list. If the page is repeatedly accessed, it is moved to the active list. The Linux operating system continuously moves pages between the active and inactive lists based on their usage patterns.

The key concept behind this repository is that every page, whether created by a program or read from disk, begins in the inactive list (assuming it is not already in cache). The tool tracks the inactive list by creating dummy files of 4K and monitoring if these pages remain in the LRU list.

By knowing the creation time of these dummy files, we can determine the oldest file that still resides in memory, giving us insight into the pages that have been cached the longest.

# Motivation

Some applications heavily rely on the performance benefits of caching. For such applications, it is crucial to have a tool that provides the current cache retention time for pages accessed through read or write operations. In other words, a metric that can indicate how long the server guarantees to have certain pages in its page cache.

This metric is important because certain applications generate new content (writes) that is quickly consumed (reads). A great example is Kafka, where producers continually write new pages (produce records) and multiple consumers read these records.

In such scenarios, it becomes critical to understand the server's current cache status. This visibility helps identify performance issues, as reading from memory takes only nanoseconds compared to reading from disk, which takes milliseconds. Additionally, this metric can provide valuable insights for resource allocation decisions.

I attempted to find a way to obtain this metric through eBPF (Extended Berkeley Packet Filter), but unfortunately, I couldn't find a method to track the eviction time of pages in the inactive list of the LRU. As a workaround, the idea is to gather this information using user space tools or techniques.


# Compatibility 
Linux OS as it relies on the LRU lists (active and inactive) algorithm 



# Technical details

## How does the tool knows if the page is memory?
It uses the [mincore()](https://man7.org/linux/man-pages/man2/mincore.2.html) system call via a python C module.

## Is it expensive in terms of performance?
This tool is designed to consume minimal resources. It achieves this by creating files of 4K size at regular time intervals. The creation time of each file is derived from the filename itself. This approach allows for efficient tracking of cache retention time, as it only requires a single `readdir()` system call instead of multiple `stat()` calls.

Additionally, the tool sorts the list of files to quickly identify expired or non-cached files. This optimization ensures that the tool can promptly identify and delete files that have been evicted from the cache.


# Installation

Via pip:
```console
foo@bar:~# pip install pagecache_ttl
```


Local in this repository root:
```console
foo@bar:~# pip install -e .
```

# Example
```console
foo@bar:~# /usr/local/bin/pagecache --help
usage: pagecache [-h] [--tmp-dir TMP_DIR]
                 [--interval-seconds INTERVAL_SECONDS]
                 [--max-time-window-seconds MAX_TIME_WINDOW_SECONDS]
                 [--daemon] [--send-metrics-to-dogstatsd]
                 [--log-level {INFO,WARNING,DEBUG}] [--log-file LOG_FILE]

PageCache TTL

optional arguments:
  -h, --help            show this help message and exit
  --tmp-dir TMP_DIR     Sets the tmp directory wher ehte program stores the
                        tracking dummy files.
  --interval-seconds INTERVAL_SECONDS
                        Sets the interval to check oldest cached sample (in
                        seconds)
  --max-time-window-seconds MAX_TIME_WINDOW_SECONDS
                        Sets the maximum time to check keep track of page
                        cache (in seconds)
  --daemon              Execute the program in daemon mode.
  --send-metrics-to-dogstatsd
                        Send metrics to local DogStatsD
                        https://docs.datadoghq.com/developers/dogstatsd/
  --log-level {INFO,WARNING,DEBUG}
                        Sets the debug level
  --log-file LOG_FILE   Sets the tmp directory wher ehte program stores the
                        tracking dummy files.
```


# Real life example
Kafka is a great example of a distributed system that provides real-time processing of data. In Kafka, there are multiple producers that continuously write new data into memory, and there are also several consumers that read and process the data.

With the help of metrics, we can determine whether the consumers will read data from memory or disk by analyzing the consumer group lag. This lag represents the time between when a message is produced and when it gets consumed by the consumer group. By monitoring this metric, we get insights into the system's performance and can predict whether data will be read from memory or disk.

Furthermore, we can use time as a dimension to assess the overall performance of the servers. By analyzing the total time the server retains old produced records, we can dimension the servers accordingly and optimize their configuration for improved efficiency and resource utilization.
We can see an exmaple which is reporting the Minimal time of cached pages of a Kafka broker in seconds
<img width="1700" alt="Screenshot 2023-12-01 at 05 02 52" src="https://github.com/sciclon2/pagecache_ttl/assets/74413315/cd05ad33-11ef-4352-b98e-0bfdbc22bc35">
