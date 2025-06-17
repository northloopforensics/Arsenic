
"""
Arsenic - A forensic analysis tool for iOS and Android devices
Copyright (C) 2025 North Loop Consulting, LLC 
Charlie Rubisoff

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os
import sys
from src.ui.app import App
# interactionC - done
# exif for heic - done
# android stuff ;)
# Timeline is broken
# Scale thumbnail to window
# large num of thumbnails is glitchy
# wifi netowork history



if __name__ == "__main__":
    app = App()
    app.mainloop()
    
    # Close the log file
    # sys.stdout.close()