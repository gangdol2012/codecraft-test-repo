#include <stdio.h>
#include <string.h>

int main(void) {
    char name[100];

    printf("Enter your name: ");
    if (fgets(name, sizeof(name), stdin) != NULL) {
        name[strcspn(name, "\n")] = '\0';
    } else {
        name[0] = '\0';
    }

    if (strlen(name) == 0) {
        strcpy(name, "Developer");
    }

    printf("Hello, %s from C!\n", name);
    return 0;
}
