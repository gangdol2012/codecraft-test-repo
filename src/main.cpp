#include <iostream>
#include <string>

int main() {
    std::string name;

    std::cout << "Enter your name: ";
    std::getline(std::cin, name);

    if (name.empty()) {
        name = "Developer";
    }

    std::cout << "Hello, " << name << " from C++!" << std::endl;
    return 0;
}
