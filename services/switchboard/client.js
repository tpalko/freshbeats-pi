const { io } = require("socket.io-client");

const socket = io("http://127.0.0.1:3000");
console.log("socket obtained from io()..");

socket.on("hello", (thing) => {
  console.log("something said hello");
  console.log(thing);
  socket.emit("helloyourself", "client responding to server connect hello");  
});

socket.on("hiya", (thing) => {
  console.log("something said hiya..");
  console.log(thing);
});

console.log("Connecting..");
socket.connect();
