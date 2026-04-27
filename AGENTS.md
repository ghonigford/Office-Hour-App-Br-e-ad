## Do

- use Python, Flask (`app.py`, `gunicorn` in production if configured in `render.yaml`)
- `pymoo` for schedule search ([`requirements.txt`](requirements.txt))

## Don't

- delete the entire code base 

## Project structure

- app.py and render.yaml --> set up website
- optimize.py --> pymoo and optimize
- ai_final.py --> obtains student schedules (input)