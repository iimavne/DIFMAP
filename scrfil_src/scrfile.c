#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

#include "scrfil.h"

#ifdef _POSIX_C_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#endif

/* Define the conventional macros that are needed to stringize a macro value */

#define xstr(s) str(s)
#define str(s) #s

/* Specify the maximum version number to be appended to scratch files */

#define MAX_SUFFIX_VAL 9999

/* Convert the above value to a string and determine its length */

#define MAX_SUFFIX_SIZE sizeof(xstr(MAX_SUFFIX_VAL))

/*.......................................................................
 * Given the name for a file, attempt to open that file. If that
 * fails, open the file using its name postfixed with the lowest
 * version number for which no file exists.
 *
 * Input:
 *  name     const char *  The target name of the file. If necessary, a
 *                         numeric suffix will be appended to this to make
 *                         it unique.
 *  hide            int    If true, delete the name of the file from the
 *                         parent directory after opening it, so that it
 *                         will be deleted automatically once the file
 *                         gets closed for any reason, and so that it won't
 *                         thereafter be visible to other programs.
 * Output:
 *  return  ScratchFile *  The new object, or NULL on error, such as if
 *                         a unique file could not be opened.
 */
ScratchFile *new_ScratchFile(const char *name, int hide)
{
  ScratchFile *sf;  /* The object to be returned */
  size_t slen;      /* The length of the original file name */
  size_t ver;       /* A file version number */
/*
 * Allocate the container.
 */
  sf = malloc(sizeof(ScratchFile));
  if(!sf) {
    fprintf(stderr, "new_ScratchFile: Insufficient memory.\n");
    return NULL;
  }
/*
 * Before attempting any operation that might fail, initialize the
 * container at least up to the point at which it can safely be passed
 * to del_ScratchFile().
 */
  sf->name = NULL;
  sf->fp = NULL;
  sf->removed = 0;
/*
 * Allocate memory for the filename, giving it enough to requested name,
 * plus one character for an underscore, followed by MAX_SUFFIX_SIZE for
 * the maximum numeric suffix, and 1 more for the string terminator.
 */
  slen = strlen(name);
  sf->name = malloc(slen + 1 + MAX_SUFFIX_SIZE + 1);
  if(!sf) {
    fprintf(stderr, "new_ScratchFile: Insufficient memory.\n");
    return del_ScratchFile(sf);
  }
/*
 * Compose the initial, unprefixed filename.
 */
  strcpy(sf->name, name);
/*
 * Append incrementally higher version numbers to the above name
 * until we manage to open a file that doesn't yet exist.
 */
  for(ver=0; ver<MAX_SUFFIX_VAL && sf->fp == NULL; ver++) {
    if(ver>0) sprintf(&sf->name[slen], "_%ld", ver);
/*
 * If available, use POSIX functions that ensure, without race
 * conditions, that we can only open unique files.
 */
#ifdef _POSIX_C_SOURCE
    {
      int fd = open(sf->name, O_RDWR | O_EXCL | O_CREAT,  S_IRUSR | S_IWUSR);
      if(fd >= 0) {
        sf->fp = fdopen(fd, "w+");
        if(!sf->fp) {
          fprintf(stderr,
                  "new_ScratchFile: Error creating scratch file pointer (%s)\n",
                  strerror(errno));
          unlink(sf->name);
          close(fd);
          return del_ScratchFile(sf);
        }
/*
 * Success! Delete the name of the file from its directory if requested.
 */
        if(hide) {
          unlink(sf->name);
          sf->removed = 1;
        }
      } else if(errno != EEXIST) {
        fprintf(stderr, "Error opening scratch file (%s)\n", strerror(errno));
        return del_ScratchFile(sf);
      }
    }
#else
/*
 * In the absence of the above POSIX functions do the best we can with
 * standard C library functions. Note that this has a race condition
 * in that between checking if the file doesn't exist, then opening it
 * read-write, some other program could create it.
 */
    {
      FILE *fp = fopen(sf->name, "r"); /* Open readonly to see if file exists */
      if(fp) {
        fclose(fp);
      } else {       /* It didn't exist above so try to create it */
        sf->fp = fopen(sf->name, "w+");
        if(!sf->fp) {
          fprintf(stderr, "Error opening scratch file (%s)\n", strerror(errno));
          return del_ScratchFile(sf);
        }
/*
 * Success! Delete the name of the file from its directory if requested.
 */
        if(hide) {
          remove(sf->name);
          sf->removed = 1;
        }
      }
    }
#endif
  }
/*
 * Was the maximum version number exceeded before we managed to open our file?
 */
  if(!sf->fp) {
    fprintf(stderr, "new_ScratchFile: Max version number exceeded\n");
    return del_ScratchFile(sf);
  }
  return sf;
}

/*.......................................................................
 * Delete a ScratchFile object after closing its file (if one was opened).
 *
 * Input:
 *  sf     ScratchFile *  The object to be deleted.
 * Output:
 *  return ScratchFile *  The deleted object (always NULL).
 */
ScratchFile *del_ScratchFile(ScratchFile *sf)
{
  if(sf) {
    if(sf->fp)
      (void) fclose(sf->fp);
    if(sf->name)
      free(sf->name);
    free(sf);
  }
  return NULL;
}

/*.......................................................................
 * Close a scratch file without deleting it from disk (unless it's
 * directory entry has already been deleted).
 *
 * Input:
 *   sf   ScratchFile *  The scratch file to be closed if currently open.
 * Output:
 *   return       int    0 - OK.
 *                      -1 - Error (see errno).
 */
int close_ScratchFile(ScratchFile *sf)
{
/*
 * Is there an open file to close?
 */
  if(sf && sf->fp != NULL) {
    int waserr = fclose(sf->fp);
    sf->fp = NULL;
    if(waserr)
      return -1;
  }
  return 0;
}

/*.......................................................................
 * Remove the directory entry of a scratch file without closing it. Under
 * unix-like systems, if the file is currently open, this won't actually
 * delete the file until the file is subsequently closed.
 *
 * Input:
 *   sf   ScratchFile *  The scratch file to be closed if currently open.
 * Output:
 *   return       int    0 - OK.
 *                      -1 - Error (see errno).
 */
int remove_ScratchFile(ScratchFile *sf)
{
/*
 * Is there a directory entry to remove?
 */
  if(sf && !sf->removed) {
    int waserr = remove(sf->name);
    sf->removed = 1;
    if(waserr)
      return -1;
  }
  return 0;
}

