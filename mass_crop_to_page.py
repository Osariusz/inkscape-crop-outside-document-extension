#!/usr/bin/env python3
"""
Mass Crop to Page - Inkscape Extension
Creates a rectangle the size of the document page and performs intersection
with all paths in the current document.

Adjusted so the clip rectangle accounts for ancestor group translations.
"""

import inkex
from inkex import PathElement, Rectangle
from inkex.paths import Path, CubicSuperPath
from inkex.transforms import Transform
import copy

class MassCropToPage(inkex.EffectExtension):

    def effect(self):
        svg = self.document.getroot()
        # Get the page bounding box
        page_bbox: BoundingBox = self.svg.get_page_bbox()
        page_left = page_bbox.left
        page_top = page_bbox.top
        page_width = page_bbox.width
        width = page_width
        page_height = page_bbox.height
        height = page_height

        # Now create your path for rectangle over that bbox
        rect_path = f"M{page_left},{page_top} " \
                    f"L{page_left + page_width},{page_top} " \
                    f"L{page_left + page_width},{page_top + page_height} " \
                    f"L{page_left},{page_top + page_height} Z"
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

    def get_ancestor_translation(self, element):
        """
        Walk up the ancestor chain and accumulate translation components
        from ancestor transform attributes.

        We only extract the translation (e, f) from the 2D affine matrix and
        sum them. This avoids computing or applying inverse transforms,
        and matches 'positions of groups' as requested.
        """
        tx = 0.0
        ty = 0.0

        parent = element.getparent()
        while parent is not None:
            tr = parent.get('transform')
            if tr:
                try:
                    T = Transform(tr)
                    # In the 2D matrix a b c d e f, e and f are the translation
                    tx += float(T.e)
                    ty += float(T.f)
                except Exception:
                    # If transform can't be parsed safely, ignore it
                    pass
            parent = parent.getparent()

        return tx, ty

    def apply_clip_to_path(self, path, width, height):
        """Apply clip path to element as an alternative to boolean operations"""

        # Compute cumulative translation of ancestor groups for this element
        tx, ty = self.get_ancestor_translation(path)

        # Create clip path
        clip_id = self.svg.get_unique_id('clip_')
        clip_path = inkex.ClipPath()
        clip_path.set('id', clip_id)

        # Make explicit that the clip coordinates are in userSpaceOnUse
        # so we know how to position the rectangle relative to the element's
        # own user coordinate system.
        clip_path.set('clipPathUnits', 'userSpaceOnUse')

        # Create rectangle for clip path.
        # We offset the rectangle by -tx, -ty so that when the clipPath is
        # interpreted in the *element's* user coordinate system it lines up with
        # the document page (0,0)-(width,height).
        rect = Rectangle()
        rect.set('x', str(-tx))
        rect.set('y', str(-ty))
        rect.set('width', str(width))
        rect.set('height', str(height))

        clip_path.append(rect)
        # Ensure defs exists and append the clipPath there
        if self.svg.defs is None:
            self.svg.append(inkex.Defs())
        self.svg.defs.append(clip_path)

        # Apply clip path to the element (use url(#id) reference)
        path.set('clip-path', f'url(#{clip_id})')

if __name__ == '__main__':
    MassCropToPage().run()
