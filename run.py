#!/usr/bin/env python3
"""
Assistive Vision System - Entry Point
Voice-controlled object detection, distance estimation, and GPS navigation.
"""
from main_controller import MainController

if __name__ == "__main__":
    controller = MainController()
    controller.start()
