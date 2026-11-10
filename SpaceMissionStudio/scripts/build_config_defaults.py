#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Write spacemissionstudio/config/defaults.yaml from the parameter
registry (transparency audit, Phase 3b). Run it after declaring or
changing a parameter; tests/test_config.py fails while the file is out of
date."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spacemissionstudio.config import files, registry  # noqa: E402

if __name__ == "__main__":
    files.DEFAULTS_FILE.write_text(files.defaults_yaml(), encoding="utf-8")
    print(f"{files.DEFAULTS_FILE.name}: {len(registry.parameters())} parameters")
