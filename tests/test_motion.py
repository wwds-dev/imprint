"""Calm rule D5 (spec manuscript-redesign, measure 7; ADR 0006, decision 7).

Motion only through ui/motion.py: at most 300 ms, never a loop, none while a
text field outside the animated widget has focus, none at all under Reduce
Motion. The drawer's own cases are in tests/test_shell.py.
"""

import pytest

from ui import motion


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widgets(qapp):
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
    root = QWidget()
    layout = QVBoxLayout(root)
    target = QWidget(root)
    field = QLineEdit(root)
    inner = QLineEdit(target)
    layout.addWidget(target)
    layout.addWidget(field)
    root.show()
    qapp.processEvents()
    # Showing a window focuses its first field; start with nobody typing.
    focused = qapp.focusWidget()
    if focused is not None:
        focused.clearFocus()
    qapp.processEvents()
    yield root, target, field, inner
    motion.stop_all()
    root.close()
    root.deleteLater()
    qapp.processEvents()


@pytest.fixture
def motion_allowed(monkeypatch):
    monkeypatch.setattr(motion, "system_reduce_motion", lambda: False)
    monkeypatch.setattr(motion, "in_app_setting", lambda: False)


def _wait_until(qapp, predicate, ms=2000):
    from PySide6.QtCore import QElapsedTimer
    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < ms:
        qapp.processEvents()
    return predicate()


def test_one_animation_starts_within_the_limits(qapp, widgets, motion_allowed):
    _root, target, _field, _inner = widgets
    seen = []
    animation = motion.animate(target, 0.0, 1.0, 160, seen.append)
    assert animation is not None
    assert motion.running() == [animation]
    assert animation.duration() <= motion.MAX_MS
    assert animation.loopCount() == 1
    assert _wait_until(qapp, lambda: not motion.running())
    assert seen and seen[-1] == 1.0


def test_nothing_runs_when_motion_is_reduced(qapp, widgets, monkeypatch):
    _root, target, _field, _inner = widgets
    monkeypatch.setattr(motion, "system_reduce_motion", lambda: False)
    monkeypatch.setattr(motion, "in_app_setting", lambda: True)
    seen, done = [], []
    assert motion.animate(target, 0, 10, 160, seen.append,
                          on_finished=lambda: done.append(1)) is None
    assert motion.running() == []
    assert seen == [10] and done == [1]          # the end state, at once


def test_the_system_setting_alone_also_stops_motion(qapp, widgets, monkeypatch):
    _root, target, _field, _inner = widgets
    monkeypatch.setattr(motion, "system_reduce_motion", lambda: True)
    monkeypatch.setattr(motion, "in_app_setting", lambda: False)
    assert motion.reduced()
    assert motion.animate(target, 0, 1, 100, lambda _v: None) is None


def test_longer_than_300_ms_or_a_loop_is_refused(widgets, motion_allowed):
    _root, target, _field, _inner = widgets
    with pytest.raises(ValueError):
        motion.animate(target, 0, 1, 301, lambda _v: None)
    with pytest.raises(ValueError):
        motion.animate(target, 0, 1, 100, lambda _v: None, loops=-1)
    assert motion.running() == []


def test_hiding_the_widget_mid_animation_stops_it(qapp, widgets, motion_allowed):
    _root, target, _field, _inner = widgets
    motion.animate(target, 0.0, 1.0, 300, lambda _v: None)
    assert motion.running()
    target.hide()
    qapp.processEvents()
    assert motion.running() == []


def test_nothing_moves_while_a_field_outside_has_focus(qapp, widgets,
                                                       motion_allowed):
    _root, target, field, _inner = widgets
    field.setFocus()
    qapp.processEvents()
    if qapp.focusWidget() is not field:
        pytest.skip("this platform gave the field no focus")
    seen = []
    assert motion.animate(target, 0, 5, 160, seen.append) is None
    assert motion.running() == [] and seen == [5]


def test_a_field_inside_the_animated_widget_does_not_stop_it(qapp, widgets,
                                                             motion_allowed):
    _root, target, _field, inner = widgets
    inner.setFocus()
    qapp.processEvents()
    if qapp.focusWidget() is not inner:
        pytest.skip("this platform gave the field no focus")
    assert motion.animate(target, 0, 5, 160, lambda _v: None) is not None


def test_stop_all_empties_the_registry(qapp, widgets, motion_allowed):
    _root, target, _field, _inner = widgets
    motion.animate(target, 0.0, 1.0, 300, lambda _v: None)
    motion.stop_all()
    assert motion.running() == []


def test_the_system_setting_is_false_offscreen():
    motion.forget_system_setting()
    assert motion.system_reduce_motion() is False
    motion.forget_system_setting()


def test_the_system_read_never_raises(monkeypatch):
    import ctypes
    monkeypatch.setattr(motion.sys, "platform", "darwin")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    def boom(*_a, **_k):
        raise OSError("no AppKit")
    monkeypatch.setattr(ctypes.cdll, "LoadLibrary", boom)
    assert motion._read_system_setting() is False


def test_the_system_setting_is_read_again_on_activation(qapp, monkeypatch):
    from PySide6.QtCore import Qt
    reads = []
    monkeypatch.setattr(motion, "_read_system_setting",
                        lambda: reads.append(1) or False)
    motion.forget_system_setting()
    motion.system_reduce_motion()
    motion.system_reduce_motion()
    assert len(reads) == 1                       # cached between activations
    motion.install(qapp)
    qapp.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    motion.system_reduce_motion()
    assert len(reads) == 2
    motion.forget_system_setting()


def test_the_in_app_setting_round_trips():
    try:
        motion.set_in_app_setting(True)
        assert motion.in_app_setting() is True
        motion.set_in_app_setting(False)
        assert motion.in_app_setting() is False
    finally:
        motion.set_in_app_setting(False)
