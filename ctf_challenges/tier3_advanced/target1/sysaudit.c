#include <stdlib.h>
#include <unistd.h>
int main() {
    setuid(0);
    setgid(0);
    system("uname -a");
    system("service_status");
    return 0;
}
