from __future__ import annotations

from ingesta.plugins.eeg8.plugin import EEG8Plugin
from ingesta.plugins.ecg1.plugin import ECG1Plugin

REGISTRY = {
    "eeg8_v0": EEG8Plugin(),
    "ecg1_v0": ECG1Plugin(),
}
