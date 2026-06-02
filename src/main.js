// Welcome to CodeCraft IDE
// Now with native browser execution!

console.log("Hello, World!");

function greet(name) {
  return `Hello, ${name}!`;
}

const user = "Developer";
console.log(greet(user));

// Try some modern JS features
const items = [1, 2, 3, 4, 5];
const doubled = items.map(n => n * 2);
console.log("Doubled items:", doubled);