// SPDX-License-Identifier: GPL-2.0-or-later
// "Start timing:" lines in the log: seconds since Play was pressed. The launcher sets BB_START_TIME
// (seconds since 1970), or run.py when it runs by itself; run.py's own lines use the same format.
#ifndef BBPORT_START_TIMING_H
#define BBPORT_START_TIMING_H

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static inline void bb_start_timing(const char* label) {
    const char* start = getenv("BB_START_TIME");
    struct timespec now;
    if (!start || !*start || !timespec_get(&now, TIME_UTC)) {
        return;
    }
    printf("Start timing: %s at %.1f s\n", label, (double)now.tv_sec + now.tv_nsec / 1e9 - atof(start));
}

#endif
