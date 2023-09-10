# pagecache_ttl

# Motivation

The are some applications which strongly rely on responding from cache for a decent performance.
I tried to find a tool which provides the current cache retention time of the pages accessed via  READ or WRITE operation, I mean basically a metric of a server saying “ I guarantee I have the last X minutes in page cache”

Why? There are some applications which generate new content (WRITES) and the are consumed very quick (READS) .
A perfect example is Kafka which have several producers writing new pages in memory (produce records) and several consumers reading these records.

So in this case is critical to understand what is the current server status in order to give visibility to performance issues (remember reading from memory means nanoseconds versus reading from disk in miliseconds)
Also this metric can give us a clearer view while adding more resources.

I tried to find a way to get this metric via eBPF but I did not find any way to track the “eviction time” of pages in the inactive list of the LRU, so the idea is to get this information via “user land”


# Compatibility 
Linux OS as it relies on the LRU lists (active and inactive) algorithm 



# Overview
Memory administration is a very complex topic, basically the Kernel OS maintains 2 LRU list for keeping pages in memory (cached) in order to reduce the disk access.
The 2 LRU lists are called inactive and active. 

When a page is accessed or created by a user-space program it Is put in the head of the inactive set. When it is accessed repeatedly, it is moved to the active list. Linux moves the pages from the active set to the inactive set as needed.

So the idea behind this repo is “page will always start in the inactive list” no matter if they were created or they are read from disk (supposing they are not in cache)
What this tool does is to keep track of the inactive LRU list, it creates dummy files of 4K and tracks if the pages are still in the LRU list.
Knowing the file creation time we can know what is the oldest created file that still remains in memory.


# Technical details

## How does the tool knows if the page is memory?
It uses the [mincore()](https://man7.org/linux/man-pages/man2/mincore.2.html) system call via a python C module.

## Is it expensive in terms of performance?
This tool consumes almost nil resources. It creates files of 4K every X time interval we use, the creation time is read from the filename so we use one readdir() system call instead of several stat()
Also it sorts the file lists in order to find the expired or non-cached file as quick as possible and delete the evicted files.


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
Kafka is a perfect example, we see in “real time” 

Kafka is a perfect one, This distributed system has several producers which are constantly writing new pages in memory, then there are several consumers which read the produced records. With this metric we will be able  to predict if consumers will read either from memory or disk knowing the consumer group lag.
Also with can dimension the servers based on the “time” in the total time the server is retaining of old produced records.
