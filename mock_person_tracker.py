import logging
import time
import random
import threading

from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockBox:
    """Mock implementation of YOLO box object."""

    def __init__(self, data):
        self.data = data


class MockResult:
    """Mock implementation of YOLO result object."""

    def __init__(self, boxes=None, orig_img=None):
        self.boxes = boxes
        self.orig_img = orig_img
        self.last_detection_time = time.time()


class MockPersonTracker(threading.Thread):
    def __init__(
        self,
        video_source="people_top.mp4",
        width=1280,
        height=720,
    ):
        """Initialize the mock person tracker with similar parameters as the original."""
        super(MockPersonTracker, self).__init__()
        self.daemon = True  # Thread will exit when main program exits

        # Configuration
        self.config = Config(
            data_dict={
                "video_source": video_source,
                "width": width,
                "height": height,
                "area_conrners": [
                    [(100, 100), (200, 100), (200, 200), (100, 200)],
                    [(300, 300), (400, 300), (400, 400), (300, 400)],
                    [(500, 500), (600, 500), (600, 600), (500, 600)],
                    [(700, 700), (800, 700), (800, 800), (700, 800)],
                ],
            },
            config_file_name="person_tracker_config.json",
        )

        # Video settings (simulated)
        self.video_source = video_source
        self.desired_width = width
        self.desired_height = height

        # FPS calculation
        self.prev_fps_calc_time = time.time()
        self.frame_count_for_fps = 0
        self.display_fps = 0

        self.last_detection_time = time.time()

        # Area definitions
        self.areas = self.config.data_dict.get("area_conrners")

        self.inside_area_counts = [0] * len(self.areas)

        # Display settings
        self.show_visualization = True

        # Thread control
        self.running = False

        # Mock specific settings
        self.mock_track_ids = list(range(1, 11))  # Track IDs 1-10
        self.mock_detection_probability = 0.8  # 80% chance of detection per frame
        self.mock_fps = 30
        self.frame_count = 0

    def stop(self):
        """Stop the tracking thread."""
        self.running = False
        logger.info("Mock tracker stopped")

    def run(self):
        """Main thread function that simulates the tracking loop."""
        self.running = True
        logger.info("Mock tracker started")

        while self.running:
            # Create a mock frame (solid color background)
            self.frame_count += 1

            # Update FPS calculation
            self._update_fps()

            # Process detections
            self._process_detections()

            # Simulate frame rate
            time.sleep(1 / self.mock_fps)

    def _update_fps(self):
        """Update FPS calculation."""
        if self.show_visualization:
            self.frame_count_for_fps += 1
            current_time = time.time()
            if current_time - self.prev_fps_calc_time >= 0.5:
                self.display_fps = self.frame_count_for_fps / (
                    current_time - self.prev_fps_calc_time
                )
                self.frame_count_for_fps = 0
                self.prev_fps_calc_time = current_time

    def _process_detections(
        self,
    ):
        """Process mock detections."""
        self._draw_tracks_and_count()
    def _draw_tracks_and_count(self):
        """Simulate drawing tracks and counting people in areas."""
        self.inside_area_counts = [0] * len(self.areas)
        # self.inside_area_counts=[1,0,0,0]
        # if time.time() - self.last_detection_time > 1:
        for idx, area in enumerate(self.areas):
                self.inside_area_counts[idx] = random.randint(
                0, 4
            )  # Mock counts for each area
            # self.last_detection_time = time.time()
    def display_loop(self):
        pass

    def start_all_in_background(self):
        """Start both tracking and display in background threads."""
        import threading

        # Start tracking thread
        self.start()  # This is already a thread

        # Create a UI thread
        self.ui_thread = threading.Thread(target=self._ui_thread_function)
        self.ui_thread.daemon = True
        self.ui_thread.start()

        logger.info("Started mock tracker and UI threads")

    def _ui_thread_function(self):
        """Function to run in the UI thread that handles simulated display."""
        logger.info("Mock UI thread started")
        self.display_loop()


# Example usage
if __name__ == "__main__":
    # Create mock tracker instance
    tracker = MockPersonTracker(
        video_source="people_top.mp4",  # This is just for configuration
        width=1280,
        height=720,
    )

    # Start tracking in background
    tracker.start_all_in_background()

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping tracker")
        tracker.stop()
