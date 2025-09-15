import p5 from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";

if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}

const sketch = (p) => {
  const boxSize = 50;
  const gridConfig = {
    size: 500,
    divisions: 20,
    get step() { return this.size / this.divisions; }
  };

  let boxPosition = { x: 0, y: -boxSize / 2, z: 0 };
  // Separate object for GUI to control during drag
  let previewPosition = { x: 0, z: 0 };
  let isDragging = false;

  const snapToGrid = (value) => {
    return Math.round(value / gridConfig.step) * gridConfig.step;
  };

  p.setup = () => {
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);

    // Initialize previewPosition to match the actual boxPosition
    previewPosition.x = boxPosition.x;
    previewPosition.z = boxPosition.z;

    const gui = new GUI();
    const limit = gridConfig.size / 2 - boxSize / 2;
    const controllerX = gui.add(previewPosition, 'x', -limit, limit)
      .name('Box X');
    const controllerZ = gui.add(previewPosition, 'z', -limit, limit)
      .name('Box Z');

    const startDragging = () => { isDragging = true; };
    
    controllerX.onChange(startDragging);
    controllerZ.onChange(startDragging);

    controllerX.onFinishChange(value => {
      // On drag end, update the real box position
      boxPosition.x = snapToGrid(value);
      // Sync the preview state back to the snapped position
      previewPosition.x = boxPosition.x;
      isDragging = false;
      // Refresh the GUI to show the snapped value
      controllerX.updateDisplay();
    });

    controllerZ.onFinishChange(value => {
      boxPosition.z = snapToGrid(value);
      previewPosition.z = boxPosition.z;
      isDragging = false;
      controllerZ.updateDisplay();
    });
  };

  const drawGrid = () => {
    p.push();
    p.stroke(150);
    p.strokeWeight(1);
    p.beginShape(p.LINES);
    for (let i = -gridConfig.size / 2; i <= gridConfig.size / 2; i += gridConfig.step) {
      p.vertex(i, 0, -gridConfig.size / 2);
      p.vertex(i, 0, gridConfig.size / 2);
      p.vertex(-gridConfig.size / 2, 0, i);
      p.vertex(gridConfig.size / 2, 0, i);
    }
    p.endShape();
    p.pop();
  };

  const drawSnapPreview = () => {
    // Draw ghost box at the snap location of the preview position
    if (isDragging) {
      const snapX = snapToGrid(previewPosition.x);
      const snapZ = snapToGrid(previewPosition.z);

      p.push();
      p.translate(snapX, boxPosition.y, snapZ);
      p.fill(255, 0, 0, 50);
      p.stroke(255, 0, 0, 150);
      p.strokeWeight(1);
      p.box(boxSize);
      p.pop();
    }
  };

  p.draw = () => {
    p.background(200);

    // Only allow camera control when not dragging the GUI
    if (!isDragging) {
      p.orbitControl();
    }

    drawGrid();
    drawSnapPreview();

    // Draw the main box at its actual position
    p.push();
    p.translate(boxPosition.x, boxPosition.y, boxPosition.z);
    p.box(boxSize);
    p.pop();
  };

  p.doubleClicked = () => {
    p.camera();
  };

  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
