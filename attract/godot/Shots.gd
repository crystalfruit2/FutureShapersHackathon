extends Node
# Validation harness: loads Main.tscn, seeks the loop, saves frames, quits.
# Not part of the loop itself.
const TIMES := [2.0, 9.0, 18.5, 29.0, 34.0]
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
        img.save_png("%s/t%02d.png" % [out, int(t)])
        print("saved t=", t)
    get_tree().quit()
