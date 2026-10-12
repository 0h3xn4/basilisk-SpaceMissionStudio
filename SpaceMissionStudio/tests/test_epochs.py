#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
"""Tests for spacemissionstudio.schema.epochs (audit M7) -- no Basilisk import."""

from datetime import datetime

import pytest

from spacemissionstudio.engine import orbit_design
from spacemissionstudio.schema.epochs import parse_epoch_utc


@pytest.mark.parametrize("text", ["2030-01-01T12:00:00", "2030-01-01T12:00:00Z", "2030-01-01T12:00:00z",
                                  "2030-01-01T14:00:00+02:00", "2030-01-01T07:00:00-05:00", " 2030-01-01T12:00:00 "])
def test_every_way_of_writing_one_utc_instant_reads_the_same(text):
    """A 'Z' or an offset is converted to naive UTC; no suffix means UTC."""
    assert parse_epoch_utc(text) == datetime(2030, 1, 1, 12, 0, 0)


@pytest.mark.parametrize("text", ["", "yesterday", "2030-13-01T00:00:00", None, 5])
def test_text_that_is_not_an_epoch_is_refused(text):
    """Bad input raises ValueError, which validation reports."""
    with pytest.raises(ValueError):
        parse_epoch_utc(text)


def test_the_ltan_helper_accepts_a_z_epoch():
    """orbit_design.raan_for_ltan_deg raised TypeError on a 'Z' epoch, which
    broke the GUI "RAAN for LTAN" helper; it now gives the same answer as
    the plain form."""
    assert orbit_design.raan_for_ltan_deg("2030-03-20T00:00:00Z", 10.5) == pytest.approx(
        orbit_design.raan_for_ltan_deg("2030-03-20T00:00:00", 10.5))


def test_a_stop_epoch_with_an_offset_is_compared_in_utc():
    """A Mission Sequence stop epoch 01:00+02:00 is 23:00 UTC the day before:
    before a 2030-01-01T00:00Z scenario epoch, so it is refused."""
    from spacemissionstudio.schema import Command, OrbitIC, Scenario, ScenarioValidationError, SpacecraftConfig

    scenario = Scenario(
        name="epochs", epoch_utc="2030-01-01T00:00:00Z",
        spacecraft=[SpacecraftConfig(name="sat-1", orbit=OrbitIC(
            type="cartesian", position_km=[7000.0, 0.0, 0.0], velocity_km_s=[0.0, 7.5, 0.0]))],  # [km], [km/s]
        mission_sequence=[Command(kind="propagate", params={"stop_condition": "epoch",
                                                            "stop_epoch_utc": "2030-01-01T05:00:00+02:00"})],
    )
    scenario.validate()  # 03:00 UTC: after the epoch
    scenario.mission_sequence[0].params["stop_epoch_utc"] = "2030-06-01T00:00:00+02:00"
    with pytest.raises(ScenarioValidationError, match="days after the scenario epoch"):
        scenario.validate()
