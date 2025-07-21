import p5 from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";
if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}
const sketch = (p) => {
  let gui;
  let socket;

  p.setup = () => {
    p.createCanvas(400, 400);
    gui = new GUI();
    // socket = io();

    // socket.on("connect", () => {
    //   console.log("Connected to server");
    // });

    // socket.on("dmx_data", (data) => {
    //   console.log("Received DMX data:", data);
    // });
  };

  p.draw = () => {
    p.background(50);
  };
};

new p5(sketch);
