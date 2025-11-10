from pythonosc import udp_client, osc_bundle_builder, osc_message_builder
from param_processer import TSOOParamProcesser


class OSCSender:
    """
    TSOO OSC Sender class for sending OSC messages to external applications.
    Handles all OSC communication including parameter updates and position data.
    """

    def __init__(self, address: str = "127.0.0.1", port: int = 5005):
        """
        Initialize the OSC sender.

        Args:
            address: OSC server address
            port: OSC server port
        """
        self.client = udp_client.SimpleUDPClient(address=address, port=port)

    def send_message(self, address: str, value):
        """
        Send a custom OSC message.

        Args:
            address: OSC address (e.g., "/whyixd/custom/message")
            value: Value to send (can be int, float, string, list, etc.)
        """
        self.client.send_message(address, value)

    def send_parameters(self, tsoo_param: TSOOParamProcesser):
        """
        Send all TSOO parameters via OSC.

        Args:
            tsoo_param: TSOOParamProcesser instance containing target and interpolated parameters
        """
        param = tsoo_param.target_tsoo_param
        inter_param = tsoo_param.interper_tsoo_param

        # -------------------composite--------------------#
        self.client.send_message(
            "/whyixd/composite/weight",
            param["people_natrual_weight"],
        )
        self.client.send_message(
            "/whyixd/composite/level",
            param["people_natrual_weight_level"],
        )
        self.client.send_message(
            "/whyixd/composite/threshold",
            param["people_natrual_weight_level_threshold"],
        )
        self.client.send_message(
            "/whyixd/composite/interper/weight", inter_param["people_natrual_weight"]
        )

        # ---------------------people---------------------#
        self.client.send_message("/whyixd/people/counts", param["area_people_count"])
        self.client.send_message(
            "/whyixd/people/vector",
            param["people_vector"],
        )
        self.client.send_message("/whyixd/people/interper/vector", inter_param["people_vector"])

        # ---------------------light----------------------#
        self.client.send_message(
            "/whyixd/light/vector",
            param["effect_vector"],
        )
        self.client.send_message("/whyixd/light/interper/vector", inter_param["effect_vector"])

        # ---------------------wind-----------------------#
        self.client.send_message("/whyixd/wind/speed", inter_param["wind_speed"])
        self.client.send_message("/whyixd/wind/angle", param["wind_angle"])
        self.client.send_message(
            "/whyixd/wind/vector",
            param["wind_vector"],
        )
        self.client.send_message("/whyixd/wind/interper/speed", inter_param["wind_speed"])
        self.client.send_message("/whyixd/wind/interper/angle", inter_param["wind_angle"])
        self.client.send_message("/whyixd/wind/interper/vector", inter_param["wind_vector"])

    def send_positions(self, person_pos: list):
        """
        Send person positions via OSC bundle.

        Args:
            person_pos: List of (x, y) tuples representing person positions
        """
        bundle_builder = osc_bundle_builder.OscBundleBuilder(osc_bundle_builder.IMMEDIATELY)
        msg = osc_message_builder.OscMessageBuilder(address="/whyixd/people/pos")
        sorted_pos = sorted(person_pos, key=lambda x: x[0])
        
        if len(sorted_pos) < 1:
            sorted_pos = [(0.0, 0.0)]

        for idx, pos in enumerate(sorted_pos):
            msg.add_arg(idx)
            msg.add_arg(pos[0])
            msg.add_arg(pos[1])

        bundle_builder.add_content(msg.build())
        pos_message = bundle_builder.build()
        self.client.send(pos_message)

    def send_glitch_data(self, glitch_frame):
        """
        Send glitch frame data via OSC.

        Args:
            glitch_frame: Numpy array containing glitch frame data
        """
        if glitch_frame is not None:
            glitch_flaten = glitch_frame.flatten().tolist()
            self.client.send_message("/whyixd/light/glitch", glitch_flaten)
