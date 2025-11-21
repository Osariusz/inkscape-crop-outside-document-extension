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
from math import isclose

# --- helper functions (put inside your class or module) ---
def _transform_to_matrix(transform_obj):
    """
    Convert an inkex.Transform object (or None) into a 3x3 numeric matrix:
      [[a, c, e],
       [b, d, f],
       [0, 0, 1]]
    inkex.Transform instances expose a .matrix or repr like Transform(((a,c,e),(b,d,f)))
    """
    if transform_obj is None:
        return [[1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0]]
    # transform_obj.matrix or transform_obj.__repr__ gives ((a,c,e),(b,d,f))
    try:
        mm = transform_obj.matrix  # usually ((a,c,e),(b,d,f))
    except Exception:
        # fallback: try to get transform string and build Transform
        mm = Transform(str(transform_obj)).matrix

    a, c, e = mm[0]
    b, d, f = mm[1]
    return [[float(a), float(c), float(e)],
            [float(b), float(d), float(f)],
            [0.0, 0.0, 1.0]]

def _mat_mult(A, B):
    """Multiply 3x3 matrices A*B"""
    return [
        [A[0][0]*B[0][0] + A[0][1]*B[1][0] + A[0][2]*B[2][0],
         A[0][0]*B[0][1] + A[0][1]*B[1][1] + A[0][2]*B[2][1],
         A[0][0]*B[0][2] + A[0][1]*B[1][2] + A[0][2]*B[2][2]],
        [A[1][0]*B[0][0] + A[1][1]*B[1][0] + A[1][2]*B[2][0],
         A[1][0]*B[0][1] + A[1][1]*B[1][1] + A[1][2]*B[2][1],
         A[1][0]*B[0][2] + A[1][1]*B[1][2] + A[1][2]*B[2][2]],
        [0.0, 0.0, 1.0]
    ]

def _mat_inverse(M):
    """Inverse of a 3x3 affine matrix where last row is [0,0,1].
       Returns None if not invertible.
    """
    a, c, e = M[0]
    b, d, f = M[1]
    det = a * d - b * c
    if isclose(det, 0.0, abs_tol=1e-12):
        return None
    inv_det = 1.0 / det
    # inverse of [[a,c,e],[b,d,f],[0,0,1]] is:
    ai =  d * inv_det
    bi = -b * inv_det
    ci = -c * inv_det
    di =  a * inv_det
    ei = (c * f - d * e) * inv_det
    fi = (b * e - a * f) * inv_det
    return [[ai, ci, ei],
            [bi, di, fi],
            [0.0, 0.0, 1.0]]

def _apply_mat_to_point(M, x, y):
    """Apply 3x3 matrix M to point (x,y)."""
    nx = M[0][0]*x + M[0][1]*y + M[0][2]
    ny = M[1][0]*x + M[1][1]*y + M[1][2]
    return nx, ny

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

    # --- replace your apply_clip_to_path with the version below ---
    def apply_clip_to_path(self, path, width, height, page_left=0.0, page_top=0.0):
        """
        Create a clipPath that clips `path` to the rectangle
        (page_left,page_top)-(page_left+width,page_top+height),
        correctly accounting for arbitrary ancestor+own transforms.
        """
        # 1) compute cumulative transform from root -> element (include element)
        #    We'll multiply ancestor matrices in document order (root first).
        ancestors = []
        el = path
        while el is not None:
            ancestors.append(el)
            el = el.getparent()
        # ancestors is [element, parent, ..., root]; we want root..element order
        ancestors = list(reversed(ancestors))

        cum = [[1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]]
        for anc in ancestors:
            # anc.transform returns a Transform object or default Transform()
            tr = None
            try:
                tr = anc.transform if hasattr(anc, 'transform') else None
            except Exception:
                # if anything goes wrong, skip this ancestor transform
                tr = None
            m = _transform_to_matrix(tr)
            cum = _mat_mult(cum, m)

        # cum maps *element-local coords* -> *document coords*
        # we need the inverse to map document page coords to element-local coords
        inv = _mat_inverse(cum)
        if inv is None:
            # transform not invertible; fallback to translation-only approach (best effort)
            inkex.errormsg(f"Warning: non-invertible transform for element {path.get('id')}; using translation-only fallback.")
            # attempt the old tx,ty fallback (existing code path) so something still happens:
            tx = 0.0; ty = 0.0
            parent = path.getparent()
            while parent is not None:
                tr = parent.get('transform')
                if tr:
                    try:
                        T = Transform(tr)
                        tx += float(T.e)
                        ty += float(T.f)
                    except Exception:
                        pass
                parent = parent.getparent()
            rect = Rectangle()
            rect.set('x', str(-tx + page_left))
            rect.set('y', str(-ty + page_top))
            rect.set('width', str(width))
            rect.set('height', str(height))
            clip_id = self.svg.get_unique_id('clip_')
            clip_path = inkex.ClipPath()
            clip_path.set('id', clip_id)
            clip_path.set('clipPathUnits', 'userSpaceOnUse')
            clip_path.append(rect)
            if self.svg.defs is None:
                self.svg.append(inkex.Defs())
            self.svg.defs.append(clip_path)
            path.set('clip-path', f'url(#{clip_id})')
            return

        # 2) rectangle corners in document coords
        x0 = float(page_left)
        y0 = float(page_top)
        x1 = float(page_left + width)
        y1 = float(page_top)
        x2 = float(page_left + width)
        y2 = float(page_top + height)
        x3 = float(page_left)
        y3 = float(page_top + height)

        # 3) map to element-local coords using inverse
        p0 = _apply_mat_to_point(inv, x0, y0)
        p1 = _apply_mat_to_point(inv, x1, y1)
        p2 = _apply_mat_to_point(inv, x2, y2)
        p3 = _apply_mat_to_point(inv, x3, y3)

        # 4) make a path for the transformed rectangle (a polygon path)
        d = f"M{p0[0]},{p0[1]} L{p1[0]},{p1[1]} L{p2[0]},{p2[1]} L{p3[0]},{p3[1]} Z"

        # 5) create clipPath containing a path element
        clip_id = self.svg.get_unique_id('clip_')
        clip_path = inkex.ClipPath()
        clip_path.set('id', clip_id)
        clip_path.set('clipPathUnits', 'userSpaceOnUse')

        clip_shape = inkex.PathElement()
        clip_shape.set('d', d)
        clip_path.append(clip_shape)

        if self.svg.defs is None:
            self.svg.append(inkex.Defs())
        self.svg.defs.append(clip_path)

        path.set('clip-path', f'url(#{clip_id})')

if __name__ == '__main__':
    MassCropToPage().run()
