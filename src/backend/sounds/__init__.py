"""What the buzzer says: the melody of each Sound (shared/models.py), and which one cuts which.

The HAL only plays a frequency (Hal.set_buzzer); the Player here decides which frequency, at every tick:

    tones.py    notes and melodies
    player.py   which melody goes with each sound, and the Player that plays them over time
"""
