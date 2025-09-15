import p5 from "p5";
import { GUI } from "lil-gui";
import { io } from "socket.io-client";

if (process.env.NODE_ENV === "production") {
  p5.disableFriendlyErrors = true;
}

const sketch = (p) => {
  const boxDepth = 25; // Z-axis
  const boxWidth = boxDepth * 2; // X-axis
  const boxHeight = boxDepth * 2; // Y-axis

  const gridConfig = {
    cellSize: 25,
    cellsX: 20,
    cellsZ: 20,
    get sizeX() {
      return this.cellsX * this.cellSize;
    },
    get sizeZ() {
      return this.cellsZ * this.cellSize;
    },
  };

  const boxes = [
    { id: 0, name: "Box 1", x: 0, y: -boxHeight / 2, z: 0 }, // Z will be corrected in setup
  ];
  let nextBoxId = 1;
  let selectedBox = boxes[0];

  let previewPosition = { x: 0, z: 0 };
  let isDragging = false;

  // --- New Snapping Logic ---
  const snapToGridX = (value) => {
    // Snap to the nearest grid line (for even multiples)
    return Math.round(value / gridConfig.cellSize) * gridConfig.cellSize;
  };
  const snapToGridZ = (value) => {
    // Snap to the center of the nearest grid cell (for odd multiples)
    return (
      Math.floor(value / gridConfig.cellSize) * gridConfig.cellSize +
      gridConfig.cellSize / 2
    );
  };

  let boxGui, controllerX, controllerZ, boxSelector;

  const hasCollisionAt = (x, z, ignoredId = -1) => {
    return boxes.some(
      (box) =>
        box.id !== ignoredId &&
        Math.abs(x - box.x) < boxWidth &&
        Math.abs(z - box.z) < boxDepth
    );
  };

  const guiState = {
    get selectedBoxName() {
      return selectedBox ? selectedBox.name : "";
    },
    set selectedBoxName(name) {
      const box = boxes.find((b) => b.name === name);
      if (box) {
        selectedBox = box;
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
        if (controllerX) controllerX.updateDisplay();
        if (controllerZ) controllerZ.updateDisplay();
      }
    },
    addBox: () => {
      let newX = 0;
      let newZ = snapToGridZ(0); // Start at a valid snapped Z position
      while (hasCollisionAt(newX, newZ)) {
        newX += gridConfig.cellSize;
      }
      const newName = `Box ${nextBoxId + 1}`;
      const newBox = {
        id: nextBoxId,
        name: newName,
        x: newX,
        y: -boxHeight / 2,
        z: newZ,
      };
      boxes.push(newBox);
      nextBoxId++;
      guiState.selectedBoxName = newName;
      refreshBoxSelector();
    },
    removeBox: () => {
      if (boxes.length <= 1) {
        alert("Cannot remove the last box.");
        return;
      }
      const index = boxes.findIndex((b) => b.id === selectedBox.id);
      boxes.splice(index, 1);
      const newSelection = boxes[Math.max(0, index - 1)];
      guiState.selectedBoxName = newSelection.name;
      refreshBoxSelector();
    },
  };

  function refreshBoxSelector() {
    if (boxSelector) boxSelector.destroy();
    const boxNames = boxes.map((b) => b.name);
    boxSelector = boxGui
      .add(guiState, "selectedBoxName", boxNames)
      .name("Selected Box");
  }

  p.setup = () => {
    p.createCanvas(p.windowWidth, p.windowHeight, p.WEBGL);

    // Correct initial Z position for the first box
    boxes[0].z = snapToGridZ(0);

    previewPosition.x = selectedBox.x;
    previewPosition.z = selectedBox.z;

    boxGui = new GUI();
    refreshBoxSelector();
    controllerX = boxGui.add(previewPosition, "x").name("Box X");
    controllerZ = boxGui.add(previewPosition, "z").name("Box Z");
    boxGui.add(guiState, "addBox").name("Add New Box");
    boxGui.add(guiState, "removeBox").name("Remove Selected");

    const startDragging = () => {
      isDragging = true;
    };
    controllerX.onChange(startDragging);
    controllerZ.onChange(startDragging);

    const finishDragging = () => {
      if (!isDragging) return;
      const snappedX = snapToGridX(previewPosition.x);
      const snappedZ = snapToGridZ(previewPosition.z);
      if (hasCollisionAt(snappedX, snappedZ, selectedBox.id)) {
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
      } else {
        selectedBox.x = snappedX;
        selectedBox.z = snappedZ;
        previewPosition.x = selectedBox.x;
        previewPosition.z = selectedBox.z;
      }
      isDragging = false;
      controllerX.updateDisplay();
      controllerZ.updateDisplay();
    };

    controllerX.onFinishChange(finishDragging);
    controllerZ.onFinishChange(finishDragging);

    const gridGui = new GUI();
    gridGui.domElement.style.left = "0px";
    gridGui.domElement.style.right = "auto";

    const updateBoxLimits = () => {
      const limitX = gridConfig.sizeX / 2 - boxWidth / 2;
      const limitZ = gridConfig.sizeZ / 2 - boxDepth / 2;
      controllerX.min(Math.min(-1, -limitX)).max(Math.max(1, limitX));
      controllerZ.min(Math.min(-1, -limitZ)).max(Math.max(1, limitZ));
      controllerX.updateDisplay();
      controllerZ.updateDisplay();
    };

    const controllerCellsX = gridGui
      .add(gridConfig, "cellsX", 2, 100, 2)
      .name("Grid Cells X");
    const controllerCellsZ = gridGui
      .add(gridConfig, "cellsZ", 2, 100, 2)
      .name("Grid Cells Z");
    controllerCellsX.onChange(updateBoxLimits);
    controllerCellsZ.onChange(updateBoxLimits);
    updateBoxLimits();
  };

  const drawGrid = () => {
    p.push();
    p.stroke(150);
    p.strokeWeight(1);
    p.beginShape(p.LINES);
    const sizeX_half = gridConfig.sizeX / 2;
    const sizeZ_half = gridConfig.sizeZ / 2;
    for (let i = -sizeX_half; i <= sizeX_half; i += gridConfig.cellSize) {
      p.vertex(i, 0, -sizeZ_half);
      p.vertex(i, 0, sizeZ_half);
    }
    for (let i = -sizeZ_half; i <= sizeZ_half; i += gridConfig.cellSize) {
      p.vertex(-sizeX_half, 0, i);
      p.vertex(sizeX_half, 0, i);
    }
    p.endShape();
    p.pop();
  };

  const drawSnapPreview = () => {
    if (isDragging && selectedBox) {
      const snapX = snapToGridX(previewPosition.x);
      const snapZ = snapToGridZ(previewPosition.z);
      const hasCollision = hasCollisionAt(snapX, snapZ, selectedBox.id);
      p.push();
      p.translate(snapX, selectedBox.y, snapZ);
      const previewWidth = boxWidth * 1.02;
      const previewHeight = boxHeight * 1.02;
      const previewDepth = boxDepth * 1.02;
      p.push();
      p.translate(0, previewHeight / 2, 0);
      p.rotateX(p.HALF_PI);
      if (hasCollision) {
        p.fill(255, 0, 0, 70);
      } else {
        p.fill(0, 255, 0, 70);
      }
      p.noStroke();
      p.plane(previewWidth, previewDepth);
      p.pop();
      p.push();
      if (hasCollision) {
        p.stroke(255, 0, 0, 200);
      } else {
        p.stroke(0, 255, 0, 200);
      }
      p.noFill();
      p.strokeWeight(2);
      p.box(previewWidth, previewHeight, previewDepth);
      p.pop();
      p.pop();
    }
  };

  p.draw = () => {
    p.background(200);
    if (!isDragging) {
      p.orbitControl();
    }
    drawGrid();

    boxes.forEach((box) => {
      p.push();
      p.translate(box.x, box.y, box.z);
      // Highlight the selected box ONLY when the GUI is open
      if (
        selectedBox &&
        box.id === selectedBox.id &&
        boxGui &&
        !boxGui._closed
      ) {
        p.fill(230, 230, 0); // Yellowish highlight
        p.stroke(0);
        p.strokeWeight(1.5);
      } else {
        p.fill(255); // Default white
        p.stroke(0);
        p.strokeWeight(1);
      }

      p.box(boxWidth, boxHeight, boxDepth);
      p.pop();
    });

    drawSnapPreview();
  };

  p.doubleClicked = () => {
    p.camera();
  };
  p.windowResized = () => {
    p.resizeCanvas(p.windowWidth, p.windowHeight);
  };
};

new p5(sketch);
