#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#define HOME_DIR "/home/environment"
#define SAFE_PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

/*
 * Runs a command as the environment user. Installed as environment:environment
 * mode 4755. It has to be a binary because the kernel ignores the setuid bit on
 * scripts.
 *
 * setuid exec preserves the caller's real UID, so the command can still tell
 * agent from verifier through getuid() while reading files as environment.
 *
 * PATH, HOME, USER, and LOGNAME are overridden; the rest of the caller's
 * environment is inherited.
 *
 * Usage: run-as-environment <command> [args...]
 */
int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <command> [args...]\n", argv[0]);
        return 2;
    }

    /* PATH is caller-controlled, so reset it before execvp resolves the command. */
    if (setenv("PATH", SAFE_PATH, 1) != 0 ||
        setenv("HOME", HOME_DIR, 1) != 0 ||
        setenv("USER", "environment", 1) != 0 ||
        setenv("LOGNAME", "environment", 1) != 0) {
        perror("setenv");
        return 1;
    }

    if (chdir(HOME_DIR) != 0) {
        perror("chdir");
        return 1;
    }

    execvp(argv[1], &argv[1]);
    perror(argv[1]);
    return 1;
}
