extends PointLight2D
## Lantern / fire flicker.  Mirrors render.py's
##   0.44 + 0.06*sin(11t) + 0.03*sin(23t)
## Tweak the exports in the inspector - no rebuild needed.
@export var base_energy := 1.6
@export var amp_slow := 0.12
@export var amp_fast := 0.06
@export var speed_slow := 11.0
@export var speed_fast := 23.0

var _t := 0.0

func _process(delta: float) -> void:
	_t += delta
	energy = base_energy + amp_slow * sin(_t * speed_slow) + amp_fast * sin(_t * speed_fast)
