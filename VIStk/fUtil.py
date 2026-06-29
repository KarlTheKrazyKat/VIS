from tkinter import *
from tkinter.font import Font as tkfont
import sys
import re

global cfp
if str.upper(sys.platform)=="WIN32":
    cfp = 'win'
else:
    cfp = 'rasp'

class fUtil():
    def __init__(self):
        if cfp == 'win':
            self.defont = "Arial"
        else: #Liberation Sans is the Linux Available version of Arial
            self.defont = "LiberationSans"

    @staticmethod
    def mkfont(size:int,bold:bool=False,font:str="default"):
        """Creates a font string with wom fonts"""

        chosen = fUtil().defont if font == "default" else font
        return f"{chosen} {size}{' bold' if bold is True else ''}"

    @staticmethod
    def autosize(e:Event=None, relations:list[Widget]=None, offset:int=None, shrink:int=0):
        """Fit text to widget boxes. Two call modes:

        * **Setup** — ``autosize(relations=[w1, w2, ...], offset=, shrink=)`` with
          no event binds ``<Configure>`` on EVERY widget so the whole group
          re-sizes together whenever any member resizes. Call once at build time.
          (Binding only one widget makes autosize read the *others'* geometry
          stale mid-resize, leaving a path-dependent size — so bind them all.)
        * **Sizing** — ``autosize(e, relations=[...], ...)`` from a ``<Configure>``
          performs one sizing pass for that event.
        * ``autosize()`` with neither an event nor relations raises ``ValueError``.

        The sizing pass finds the largest point size at which every widget's text
        still fits its box, then applies that size to each — preserving each
        widget's own family and weight. With `relations`, all widgets share one
        size but keep their own fonts.

        Widgets are grouped by font (identical spec ⇒ identical metrics). Line
        height and the font scaling slope are identical within a group, so each
        group is measured once per size instead of once per widget; only text
        width (which depends on the string) is measured per widget — and widgets
        whose height clearly binds skip even that during the fit search.
        """
        if e is None: #Setup mode: bind <Configure> on the whole group, then done
            if relations is None:
                raise ValueError("autosize() needs an event or a relations list")
            group = list(relations)
            for w in group:
                kin = [x for x in group if x is not w] #the other members
                w.bind("<Configure>", lambda ev, _kin=kin:
                       fUtil.autosize(ev, relations=_kin, offset=offset, shrink=shrink))
            return None
        _root = e.widget.winfo_toplevel()
        geom_re = re.compile(r"(\d+)x(\d+)") #parses "WxH+X+Y" from winfo_geometry()

        widgets = [e.widget] + (list(relations) if relations is not None else [])

        #Group by font spec string. Same string => identical font (family,
        #weight, slant AND size), so each group shares one Font — created once,
        #not once per widget — and every member provably has the same current
        #size. Members are mutable lists so the seed can record each bind mode.
        groups = {} #font str -> {"font","family","weight","slant","size","members"}
        for wi in widgets:
            text = wi["text"]
            if not isinstance(text, str):
                continue
            gw, gh = geom_re.match(wi.winfo_geometry()).groups() #one Tcl call vs two
            avail_w = int(gw) - 1 - shrink
            avail_h = int(gh) - 1
            if avail_w < 1 or avail_h < 1:
                if wi is e.widget:
                    return None          #event widget not ready — bail as before
                continue                 #relation not ready — ignore this pass
            fval = wi["font"] #str or Tcl_Obj; a valid font descriptor either way
            fkey = str(fval) #hashable group key (a Tcl_Obj isn't hashable)
            grp = groups.get(fkey)
            if grp is None: #first widget of this font: build + resolve it once
                f = tkfont(_root, fval) #build from the original, not str(fval)
                spec = f.actual() #one Tcl call resolves family/weight/slant/size
                grp = groups[fkey] = {"font": f, "members": [],
                                      "family": spec["family"], "weight": spec["weight"],
                                      "slant": spec["slant"], "size": spec["size"]}
            grp["members"].append([wi, text, avail_w, avail_h, "b"]) #[..., bind mode]
        if not groups:
            return None

        #Ceiling = smallest box height, since linespace always exceeds size.
        hi = max(1, min(m[3] for g in groups.values() for m in g["members"]))

        #Seed + classify. Line height and text width both scale ~linearly with
        #size, so the height slope (S_REF/linespace) is read once per group and
        #text width once per widget; a large reference makes integer-pixel
        #rounding a negligible fraction of each slope. Each widget's two caps give
        #its max size (the smaller) AND its binding dimension — and because the
        #width:height ratio is size-independent, whichever dimension binds at the
        #seed binds at every size. With a clear margin we record it ("w"/"h") so
        #fits() can skip the other dimension (for height-bound widgets, the
        #expensive width measure); near a square match we keep "b" and check both.
        S_REF = 256
        MARGIN = 3 #size-unit gap before trusting one dimension (>=2 suffices)
        est = hi
        binding = None #(member, font) we predict binds first (smallest cap)
        for g in groups.values():
            f = g["font"]
            f.configure(size=S_REF)
            h_slope = S_REF / f.metrics("linespace") #once per group
            for m in g["members"]:
                h_cap = m[3] * h_slope #height-limited size
                mw = f.measure(m[1])
                w_cap = m[2] * S_REF / mw if mw > 0 else float("inf") #empty: no width bind
                cap = min(h_cap, w_cap)
                if cap < est: #tightest so far — the widget we expect to bind
                    est, binding = cap, (m, f)
                if   w_cap < h_cap - MARGIN: m[4] = "w" #width clearly binds
                elif h_cap < w_cap - MARGIN: m[4] = "h" #height clearly binds
        _size = max(1, min(hi, int(est)))

        def fits(size): #every widget must fit; skip its non-binding dimension
            for g in groups.values():
                f = g["font"]
                f.configure(size=size)
                ls = f.metrics("linespace") #identical for the whole group
                for _, text, avail_w, avail_h, mode in g["members"]:
                    if mode != "w" and ls > avail_h:
                        return False
                    if mode != "h" and f.measure(text) > avail_w:
                        return False
            return True

        def fits_one(m, f, size): #single widget, honoring its bind mode
            f.configure(size=size)
            if m[4] != "w" and f.metrics("linespace") > m[3]:
                return False
            if m[4] != "h" and f.measure(m[1]) > m[2]:
                return False
            return True

        #Exact correction. The seed isn't pixel-exact (integer sizes, hinting),
        #so walk to the true size — but gallop only the widget we predict binds
        #first, then confirm once against everyone. The confirm self-corrects a
        #mispredicted binder; it rarely fires, since _size is seeded at that
        #widget's own cap, so the walk is ~1 step and can't overshoot far.
        if binding is not None:
            bm, bf = binding
            if fits_one(bm, bf, _size):
                while _size < hi and fits_one(bm, bf, _size + 1):
                    _size += 1
            else:
                while _size > 1 and not fits_one(bm, bf, _size):
                    _size -= 1
            if not fits(_size): #someone else is actually tighter — walk down
                while _size > 1 and not fits(_size):
                    _size -= 1
        else: #no predicted binder (ceiling-limited): plain full-fits walk
            if fits(_size):
                while _size < hi and fits(_size + 1):
                    _size += 1
            else:
                while _size > 1 and not fits(_size):
                    _size -= 1

        if offset is not None: #Apply offset
            _size = _size - offset
        _size = max(1, _size) #Clamp: in Tk, size <= 0 means pixels/invalid

        #Apply the shared size, keeping each group's own family/weight/slant.
        #Skip groups already at _size — common mid-drag when the box wiggles but
        #the fitting size doesn't change. Members share the group's font string,
        #so the group's size is every member's current size (no desync risk).
        for g in groups.values():
            if g["size"] == _size: #already this size — nothing to do
                continue
            font = (g["family"], _size, g["weight"], g["slant"])
            for m in g["members"]:
                m[0].configure(font=font)
