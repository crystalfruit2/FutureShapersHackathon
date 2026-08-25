extends Node
## Deterministic recorder: seeks the loop frame by frame and dumps PNGs.
## Godot's Movie Maker under-reported frames here, so the loop is stepped by hand.
## Usage: Godot --path . res://Record.tscn -- <outdir> [fps] [seconds]
const DEFAULT_OUT := "res://frames"
func _ready() -> void:
	var argv := OS.get_cmdline_user_args()
	var out: String = ProjectSettings.globalize_path(argv[0] if argv.size() > 0 else DEFAULT_OUT)
	var fps: float = float(argv[1]) if argv.size() > 1 else 24.0
	var secs: float = float(argv[2]) if argv.size() > 2 else 40.0
	DirAccess.make_dir_recursive_absolute(out)
	var main: Node = load("res://Main.tscn").instantiate()
	add_child(main)
	var ap: AnimationPlayer = main.get_node("AnimationPlayer")
	ap.play("loop")
	var n := int(round(secs * fps))
	for i in n:
		ap.seek(float(i) / fps, true)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("%s/f%05d.png" % [out, i])
		if i % 120 == 0: print("frame ", i, "/", n)
	print("done ", n)
	get_tree().quit()
