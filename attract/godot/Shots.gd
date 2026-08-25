extends Node
# Validation harness: loads Main.tscn, seeks the loop, saves frames, quits.
# Not part of the loop itself.
const TIMES := [1.0, 5.0, 8.0, 12.0, 16.0, 18.5, 22.0, 26.0, 29.0, 33.0, 36.0, 39.0]
func _ready() -> void:
	var main: Node = load("res://Main.tscn").instantiate()
	add_child(main)
	var ap: AnimationPlayer = main.get_node("AnimationPlayer")
	var out := ProjectSettings.globalize_path("res://shots")
	DirAccess.make_dir_recursive_absolute(out)
	for t in TIMES:
		ap.play("loop")
		ap.seek(t, true)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var img: Image = get_viewport().get_texture().get_image()
		img.save_png("%s/t%05d.png" % [out, int(t * 100.0)])
		print("saved t=", t)
	get_tree().quit()
