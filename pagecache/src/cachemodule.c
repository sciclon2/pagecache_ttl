#include <Python.h>

#include <unistd.h>
#include <sys/mman.h>

// This module is needed in order to access the POSIX operating system API and use mincore()
// mincore() returns a vector that indicates whether pages of the
// calling process's virtual memory are resident in core (RAM), and
// so will not cause a disk access (page fault) if referenced.  The
// kernel returns residency information about the pages starting at
// the address addr, and continuing for length bytes.


static PyObject *cache_ratio(PyObject *self, PyObject *args) {
    int fd;
    void *file_mmap;
    unsigned char *mincore_vec;
    struct stat file_stat;
    ssize_t page_size = getpagesize();
    size_t page_index;
    ssize_t vec_size;

    // Validate and convert argument of FD
    if(!PyArg_ParseTuple(args, "i", &fd)) {
        return NULL;
    }

    if(fstat(fd, &file_stat) < 0) {
        PyErr_SetString(PyExc_IOError, "Could not fstat file");
        return NULL;
    }

    if ( file_stat.st_size == 0 ) {
        PyErr_SetString(PyExc_IOError, "Cannot mmap zero size file");
        return NULL;
    }

    file_mmap = mmap((void *)0, file_stat.st_size, PROT_NONE, MAP_SHARED, fd, 0);

    if(file_mmap == MAP_FAILED) {
        PyErr_SetString(PyExc_IOError, "Could not mmap file");
        return NULL;
    }

    vec_size = (file_stat.st_size + page_size - 1) / page_size;
    mincore_vec = calloc(1, vec_size);

    if(mincore_vec == NULL) {
        return PyErr_NoMemory();
    }

    if(mincore(file_mmap, file_stat.st_size, mincore_vec) != 0) {
        PyErr_SetString(PyExc_OSError, "Could not call mincore for file");
        return NULL;
    }

    int cached = 0;
    for (page_index = 0; page_index <= file_stat.st_size/page_size; page_index++) {
        if (mincore_vec[page_index]&1) {
            ++cached;
        }
    }

    free(mincore_vec);
    munmap(file_mmap, file_stat.st_size);

    int total_pages = (int)ceil( (double)file_stat.st_size / (double)page_size );
    return Py_BuildValue("(ii)", cached, total_pages);
}

static PyMethodDef CacheMethods[] = {
    {"ratio",  cache_ratio, METH_VARARGS,
     "Get cached and total pages."},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static struct PyModuleDef cachemodule = {
    PyModuleDef_HEAD_INIT,
    "cache",   /* name of module */
    NULL, /* module documentation, may be NULL */
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    CacheMethods
};

PyMODINIT_FUNC PyInit_cache(void)
{
    return PyModule_Create(&cachemodule);
};
