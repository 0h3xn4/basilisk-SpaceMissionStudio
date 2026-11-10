#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
#
"""Undo and redo of scenario edits (UX/UI guidelines, "undo and redo").

The history holds whole scenarios (``Scenario.to_dict()``, valid or not:
a scenario being built from scratch is invalid until it has a
spacecraft), one per settled edit: the main window records the scenario
once typing pauses. A field being typed in keeps its own Ctrl+Z for its
text. Loading or starting a scenario starts a new history. Undo and Redo
are labelled with what they change back (:meth:`ScenarioHistory.undo_label`).
"""

from __future__ import annotations

import copy

MAX_STEPS = 100  # undo steps kept


class ScenarioHistory:
    """A linear undo history of scenario snapshots."""

    def __init__(self, max_steps: int = MAX_STEPS):
        self._states: list[dict] = []
        self._index = -1
        self._max_steps = max_steps

    def reset(self, state: dict | None) -> None:
        """Start again from ``state`` (or from nothing)."""
        self._states = [copy.deepcopy(state)] if state is not None else []
        self._index = len(self._states) - 1

    def record(self, state: dict) -> bool:
        """Add ``state`` after the current one, dropping any redo; False if
        it equals the current state (nothing changed)."""
        if self._index >= 0 and self._states[self._index] == state:
            return False
        del self._states[self._index + 1:]
        self._states.append(copy.deepcopy(state))
        if len(self._states) > self._max_steps + 1:
            del self._states[0]
        self._index = len(self._states) - 1
        return True

    def replace_current(self, state: dict) -> None:
        """Make ``state`` the current entry without touching undo or redo
        (after a restore, the editor's own reading of the restored scenario)."""
        if self._index < 0:
            self.reset(state)
        else:
            self._states[self._index] = copy.deepcopy(state)

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return self._index < len(self._states) - 1

    def undo(self) -> dict | None:
        if not self.can_undo():
            return None
        self._index -= 1
        return copy.deepcopy(self._states[self._index])

    def redo(self) -> dict | None:
        if not self.can_redo():
            return None
        self._index += 1
        return copy.deepcopy(self._states[self._index])

    def undo_label(self) -> tuple[str, str] | None:
        """``(short, long)`` naming what :meth:`undo` would change back
        (``history.describe``); None when there is nothing to undo."""
        if not self.can_undo():
            return None
        return _label(self._states[self._index], self._states[self._index - 1])

    def redo_label(self) -> tuple[str, str] | None:
        """The same for :meth:`redo`."""
        if not self.can_redo():
            return None
        return _label(self._states[self._index], self._states[self._index + 1])


def _label(before: dict, after: dict) -> tuple[str, str]:
    from .. import history

    return history.describe(history.changes(before, after))
