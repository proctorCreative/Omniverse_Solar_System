from omniverse_solar_system.label_layout import (
    LabelCandidate,
    LabelBox,
    boxes_overlap,
    choose_non_overlapping_labels,
)


def test_box_overlap_detects_intersection_and_separation():
    assert boxes_overlap(LabelBox(0, 0, 10, 10), LabelBox(9, 9, 20, 20))
    assert not boxes_overlap(LabelBox(0, 0, 10, 10), LabelBox(10, 0, 20, 10))


def test_higher_priority_label_wins_collision():
    visible = choose_non_overlapping_labels(
        [
            LabelCandidate(0, "Mercury", 100, 100, 2.0),
            LabelCandidate(8, "Pluto", 101, 100, 10.0),
        ],
        viewport_width=400,
        viewport_height=300,
    )
    assert visible == {8}


def test_non_overlapping_labels_are_kept():
    visible = choose_non_overlapping_labels(
        [
            LabelCandidate(0, "Mercury", 50, 50, 1.0),
            LabelCandidate(1, "Venus", 250, 200, 2.0),
        ],
        viewport_width=400,
        viewport_height=300,
    )
    assert visible == {0, 1}
