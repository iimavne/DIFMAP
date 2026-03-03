#ifndef scrfil_h
#define scrfil_h

/* Scratch file utilities */

/* True if named file exists and is readable */

int file_exists(const char *name);

/* Invoke an external editor on a given file */

int ed_file(const char *name);

typedef struct {
  char *name;      /* The name of the file */
  FILE *fp;        /* The pointer to the opened file */
  int removed;     /* True if the file's directory entry has been deleted */
} ScratchFile;

ScratchFile *new_ScratchFile(const char *name, int hide);
ScratchFile *del_ScratchFile(ScratchFile *sf);
int close_ScratchFile(ScratchFile *sf);
int remove_ScratchFile(ScratchFile *sf);

#endif
