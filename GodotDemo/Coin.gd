extends Area3D

@export var points = 1

func _ready():
	# Connect the body_entered signal
	body_entered.connect(_on_body_entered)

func _process(delta):
	rotate_y(2 * delta)  # Rotate 2 radians per second

func _on_body_entered(body):
	if body.name == "Player":
		if body.has_method("add_score"):
			body.add_score(points)
		queue_free()  # Disappear (collected)
