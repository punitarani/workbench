#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define HOME_DIR "/home/environment"
#define SAFE_PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
#define ALLOWED_DIR "/usr/local/libexec/workbench/"

/*
 * Runs an allowlisted command as the environment user. Installed as
 * environment:environment mode 4755. It has to be a binary because the kernel
 * ignores the setuid bit on scripts.
 *
 * The allowlist is the point. This helper exists so the tool servers can read
 * the offstage databases that the agent cannot; if it ran arbitrary commands,
 * the agent could read them too (`run-as-environment cat .../clio.db`) and the
 * MCP surface would stop being the only aperture. So argv[1] must be an
 * absolute path to a file directly inside ALLOWED_DIR, which is owned by
 * environment and unreadable to the agent.
 *
 * setuid exec preserves the caller's real UID, so the command can still tell
 * agent from verifier through getuid() while reading files as environment.
 *
 * PATH, HOME, USER, and LOGNAME are overridden; the rest of the caller's
 * environment is inherited.
 *
 * Usage: run-as-environment /usr/local/libexec/workbench/<program> [args...]
 */
static int allowed(const char *path) {
    size_t prefix_len = strlen(ALLOWED_DIR);

    if (strncmp(path, ALLOWED_DIR, prefix_len) != 0) {
        return 0;
    }
    /* Directly inside: no nested directories, and nothing to traverse with. */
    const char *leaf = path + prefix_len;
    if (*leaf == '\0' || strchr(leaf, '/') != NULL) {
        return 0;
    }
    if (strcmp(leaf, ".") == 0 || strcmp(leaf, "..") == 0) {
        return 0;
    }
    return 1;
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s %s<program> [args...]\n", argv[0], ALLOWED_DIR);
        return 2;
    }

    if (!allowed(argv[1])) {
        fprintf(stderr, "%s: refusing to run %s: only programs directly in %s\n",
                argv[0], argv[1], ALLOWED_DIR);
        return 2;
    }

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

    /* execv, not execvp: the path is already absolute and validated, and PATH
     * resolution would reopen the door the allowlist just closed. */
    execv(argv[1], &argv[1]);
    perror(argv[1]);
    return 1;
}
