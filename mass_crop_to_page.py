#!/usr/bin/env python3
"""
Mass Crop to Page - Inkscape Extension
Creates a rectangle the size of the document page and performs intersection
with all paths in the current document.
"""

import inkex
from inkex import PathElement, Rectangle
from inkex.paths import Path, CubicSuperPath
import copy

class MassCropToPage(inkex.EffectExtension):

    def effect(self):
        # Get document dimensions
        svg = self.document.getroot()
        width = self.svg.unittouu(svg.get('width', '100px'))
        height = self.svg.unittouu(svg.get('height', '100px'))

        # Create page-sized rectangle path
        rect_path = f"M0,0 L{width},0 L{width},{height} L0,{height} Z"
        rect_csp = CubicSuperPath(Path(rect_path).to_absolute())

        # Find all path elements
        paths_list = svg.xpath('//svg:path', namespaces=inkex.NSS)

        for path in paths_list:
            try:
                # Get the path data as CubicSuperPath
                path_csp = CubicSuperPath(path.path.to_absolute())

                # Perform intersection (this is a simplified approach)
                # For complex boolean operations, we'd need additional libraries
                # This approach keeps paths that are within the rectangle bounds
                self.crop_path_to_rect(path, path_csp, rect_csp, width, height)

            except Exception as e:
                inkex.errormsg(f"Error processing path {path.get('id')}: {str(e)}")
                continue

    def crop_path_to_rect(self, path, path_csp, rect_csp, width, height):
        """Crop path to rectangle bounds using a bounding box approach"""
        try:
            # Get bounding box of the path
            bbox = path.bounding_box()

            if bbox is None:
                return

            # If path is completely outside rectangle, make it empty
           # if (bbox.left > width or bbox.right < 0 or
           #     bbox.top > height or bbox.bottom < 0):
          #      path.path = Path("")  # Empty path
          #      return

            # If path is completely inside rectangle, leave it as is
            if (bbox.left >= 0 and bbox.right <= width and
                bbox.top >= 0 and bbox.bottom <= height):
                return  # Path is already within bounds

            # For paths that cross boundaries, we need to use clip operations
            # Since direct boolean ops are problematic, we'll use a simpler approach
            # by setting clip-path (alternative method)
            self.apply_clip_to_path(path, width, height)

        except Exception as e:
            inkex.errormsg(f"Error cropping path {path.get('id')}: {str(e)}")

    def apply_clip_to_path(self, path, width, height):
        """Apply clip path to element as an alternative to boolean operations"""
        # Create clip path
        clip_id = self.svg.get_unique_id('clip_')
        clip_path = inkex.ClipPath()
        clip_path.set('id', clip_id)

        # Create rectangle for clip path
        rect = Rectangle()
        rect.set('x', '0')
        rect.set('y', '0')
        rect.set('width', str(100))
        rect.set('height', str(100))

        clip_path.append(rect)
        self.svg.defs.append(clip_path)

        # Apply clip path to the element
        path.set('clip-path', f'url(#{clip_id})')

if __name__ == '__main__':
    MassCropToPage().run()
