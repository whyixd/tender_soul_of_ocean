import p5, { toggleClass } from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";

if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}

const sketch = (p) => {
  p.setup = () => {
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);
  };
  p.draw = () => {
    p.background(200);
    p.box(50);
  };
  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
