import os
import json


class Config:
    """
    Configuration class for the application.
    """

    def __init__(self, data_dict: dict, config_file_name="config.json"):
        self.config_file_name = config_file_name
        self.data_dict = data_dict
        self.config_file_path = os.path.join(os.getcwd(), self.config_file_name)
        self.loaded_config = self.load()
        # print(self.loaded_config)

    def load(self):
        """
        Load configuration from the config file.
        """
        if os.path.exists(self.config_file_path):
            with open(self.config_file_path, "r", encoding="utf-8") as file:
                self.data_dict = json.load(file)
        else:
            print(f"Configuration file {self.config_file_name} not found.")
            self.create_default_config()
            self.load()
        return self.data_dict

    def create_default_config(self):
        """
        Create a default configuration file if it does not exist.
        """
        with open(self.config_file_path, "w", encoding="utf-8") as file:
            json.dump(self.data_dict, file, indent=4, ensure_ascii=False)
        print(f"Default configuration created at {self.config_file_name}")

    def save(self, new_data=None):
        """
        Save the current configuration to the config file.
        """
        if new_data == None:
            new_data = self.data_dict
        with open(self.config_file_path, "w", encoding="utf-8") as file:
            json.dump(new_data, file, indent=4, ensure_ascii=False)
        print(f"Configuration saved to {self.config_file_name}")


# fields = {
#     "artnet_host": "127.0.0.1",
#     "artnet_universe": 0,
#     "artnet_channels": 128,
#     "block_shape": (8, 4),
# }
# config = Config(data_dict=fields, config_file_name="config.json")
