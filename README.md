# star-goals

A real-time glowing night sky that grows as you finish your own goals.

The sky matches the real sky for your location and time. You start with an empty sky. Every goal you tick earns stars, and new stars appear on the map, brightest first. Earn enough and real constellations light up.

## Features

- Real stars from the HYG star catalog, placed for your time and location
- Soft glow and a slow twinkle on every star
- A Milky Way band that fades in as you earn stars
- Add your own goals (daily or one-time) and choose how many stars each gives
- Tick a goal to earn stars, click it again to untick
- 8 real constellations unlock as your star count grows
- New stars pulse with pink rings, and shooting stars start after 500 stars
- Everything is saved in a local file, no internet needed

## Setup

You need Python 3.

1. Install pygame-ce (use this, not plain pygame, so it works on new Python versions):

        python3 -m pip install pygame-ce

2. Copy the location file, then open `config.py` and put in your own latitude and longitude (east longitude is positive):

        cp config.example.py config.py

3. Run it:

        python3 sky.py

## Controls

- **G**: open or close the goals panel
- **Click a goal**: tick it and earn stars (click again to untick)
- **+ Add goal**: make your own goal (Tab moves between boxes, Enter saves)
- **x on a goal**: click twice to delete it (you lose the stars it gave)
- **F**: switch between fullscreen and window
- **C**: show or hide constellation lines
- **Esc**: quit

## Make it yours

- Constellation costs are in `COSTS` at the top of `sky.py`
- Shooting star settings are at the top of `shooting.py`
- Your goals and star count are saved in `data.json`, which is created on first run

## Credits

Star data comes from the HYG Database by David Nash (astronexus.com). Please check its page for its license terms.

Built by Jadebit.
