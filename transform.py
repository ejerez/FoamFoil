import numpy as np
from scipy import interpolate as si
import os
from scipy.linalg import expm, norm
import math
from copy import deepcopy
import pandas as pd

xAxis = np.array([1, 0, 0])
yAxis = np.array([0, 1, 0])
zAxis = np.array([0, 0, 1])

unit = 1000

'''
The Airfoil class contains all operation functions that can be performed on
the airfoil coordinates. It also contains get_ functions to request certain
certain properties of the airfoil.
'''
class Airfoil:

    def __init__(self, foil, name = None):
        self.name = name    # Name of the airfoil
        self.ofoil = foil   # Original foil datapoints (3d numpy array)
        self.foil = foil    # Foil datapoints (3d numpy array)
        self.qcpoint = np.array([0.25, 0., 0.]) # Quarter chord point (rotation center)
        self.lepoint = np.array([0., 0., 0.])   # Leading edge point

    '''
    get_ functions return the requested property of the class.
    '''
    def get_name(self):
        return self.name

    def get_qcpoint(self):
        return self.qcpoint

    def get_lepoint(self):
        return self.lepoint

    def get_ofoil(self):
        return self.ofoil

    def get_foil(self):
        return self.foil

    def get_name(self):
        return self.name

    def set_qcpoint(self, qc):
        self.qcpoint = np.array([qc, 0., 0.])

    def update_ofoil(self):
        self.ofoil = deepcopy(self.foil)

    '''
    The scale, rotate and translate functions modify the foil coordinates
    described by the transformations. Note that the order of the transformations
    is important. First scale, then rotate and lastly translate.
    '''

    # Scales foil with a value of factor so that the chord has the desired dimension.
    # Scaling happens with the leading edge as center.
    def scale(self, chord):
        factor = chord*2/(self.foil[0, 0] + self.foil[-1, 0])
        self.foil =  factor * (self.foil - self.lepoint) + self.lepoint
        self.qcpoint = factor * (self.qcpoint - self.lepoint) + self.lepoint

    # axis is a unit vector of the axis along which the rotation is performed.
    # theta is the angle measured counterclockwise.
    def rotate(self, axis, theta):
        if math.isnan(theta):
            return
        rotationMatrix = expm(np.cross(np.eye(3), axis/norm(axis)*theta))
        self.qcpoint = np.dot(rotationMatrix, self.qcpoint.T).T
        self.lepoint = np.dot(rotationMatrix, self.lepoint.T).T
        self.foil = np.dot(rotationMatrix, self.foil.T).T

    # axis is a unit vector of the axis along which the translation is performed.
    # dist is the distance of the translation.
    def translate(self, axis, dist):
        translationVector = axis * dist
        self.foil += translationVector
        self.lepoint += translationVector
        self.qcpoint += translationVector


    '''
    The refine function (Originally written by Eduardo J. and modified) derotates
    and normalizes the foil and makes the point distribution uniform (equal amounts
    of points on top as on lower side with a density that varies sinusoidally).
    '''
    def refine(self, npoints):
        # Interpolate leading edge curve to get an accurate estimation of the lepoint.
        u = self.foil[:, 0]
        v = self.foil[:, 2]

        leu= []
        lev = []
        # Takes small set of points near LE to find accurate LE.
        for i in range(len(u)):
            if u[i] < 0.05:
                leu.append(u[i])
                lev.append(v[i])

        # Sets up a linear point spacing and does spline interpolation of the LE curve.
        newLev = np.linspace(min(lev), max(lev), 200)
        newLeu = si.interpolate.interp1d(lev, leu, kind='cubic')(newLev)

        # Finds TE.
        teu = (u[0] + u[-1])/2
        tev = (v[0] + v[-1])/2

        c = []

        # Finds distance between every point of interpolated LE section and TE.
        for i in range(len(newLeu)):
            c.append( np.sqrt( (newLeu[i] - teu)**2 + (newLev[i] - tev)**2 ) )

        # Finds most distant point from TE (a.k.a. most accurate LE).
        ule = newLeu[np.argmax(c)]
        vle = newLev[np.argmax(c)]
        angle = -np.arctan((tev-vle)/(teu-ule))

        # Derotates the airfoil.
        self.rotate(yAxis, angle)

        # Translates so LE is at [0,0].
        self.translate(np.array([-ule, 0, -vle]), 1.)

        # Normalizes so that TE is at [1,0].
        self.scale(1)

        # Split foil into upper and lower curves.
        u = self.foil[:, 0]
        v = self.foil[:, 2]

        # Splits foil into upper and lower curves.
        for i in range(len(u)):
            if u[i] < 0.05:
                if v[i] < 0:
                    indexSplit = i
                    break

        # Flips if the foil starts on the underside.
        if v[indexSplit-1] - v[indexSplit] < 0:
            u = np.flip(u)
            v = np.flip(v)

            for i in range(len(u)):
                if u[i] < 0.05:
                    if v[i] < 0:
                        indexSplit = i
                        break

        # Adds the LE to both curves.
        ut = np.concatenate((u[:indexSplit],[0]), axis=None)
        vt = np.concatenate((v[:indexSplit],[0]), axis=None)

        ul = np.concatenate(([0],u[indexSplit:]), axis=None)
        vl = np.concatenate(([0],v[indexSplit:]), axis=None)

        ut = np.flip(ut)
        vt = np.flip(vt)

        # Makes sure npoints is even.
        if npoints % 2 != 0:
                npoints += 1

        # Sine-weighted spacing for the x distribution of interpolated points.
        # More points near TE and LE.
        uNew = [u/2 + 0.5 for u in np.sin(np.linspace(-(math.pi/2), (math.pi/2), int(npoints/2)))]

        # Akima interpolation is less susceptible to oscillations near endpoints.
        vtNew = si.Akima1DInterpolator(ut, vt)(uNew)
        vlNew = si.Akima1DInterpolator(ul, vl)(uNew)

        # Joins the two curves (excluding the LE from the lower curve to avoid duplicate) to form a single foil.
        u = np.concatenate( ( np.flip(uNew),uNew[1:] ), axis=None )
        v = np.zeros(npoints-1)
        w = np.concatenate( ( np.flip(vtNew),vlNew[1:] ), axis=None )
        self.foil = np.array([u, v, w]).T
        self.qcpoint = np.array([0.25, 0., 0.])
        self.lepoint = np.array([0., 0., 0.])


'''
The section class is responsible to house all the properties related to a wing
section. A wing section is the lofted body between two aifoil profiles. This class
is independent of machine properties
'''
class Section:

    def __init__(self, name):

        self.name = name

        self.npoints = 200

        self.chord = [1, 1]
        self.span = [0, 1]
        self.sweep = [0, 0] # Sweep offset in unit
        self.twist = [0, 0] # Twist angle in radians
        self.dihedral = [0, 0]

        self.root = None    # Airfoil1 is an instance of the AIrfoil class
        self.tip = None    # Airfoil1 is an instance of the AIrfoil class

        self.rootName = None
        self.tipName = None

        self.zOffsetRoot = 20
        self.yOffsetRoot = 100
        self.xOffsetRoot = 100

    '''
    The set_ functions are used to configure the properties of the Section
    '''
    def set_root(self, xwimpLine):
        self.span[0] = unit*xwimpLine[0]
        self.chord[0] = unit*xwimpLine[1]
        self.sweep[0] = unit*xwimpLine[2]
        self.dihedral[0] = math.radians(xwimpLine[3])
        self.twist[0] = math.radians(xwimpLine[4])
        self.rootName = xwimpLine[9]

    def set_tip(self, xwimpLine):
        self.span[1] = unit*xwimpLine[0]
        self.chord[1] = unit*xwimpLine[1]
        self.sweep[1] = unit*xwimpLine[2]
        self.dihedral[1] = math.radians(xwimpLine[3])
        self.twist[1] = math.radians(xwimpLine[4])
        self.tipName = xwimpLine[9]

    def set_npoints(self, n):
        self.npoints = n

    def set_foils(self, filePath):
        for fileName in os.listdir(filePath):
            path = os.path.join(filePath, fileName)
            with open(path, 'r') as f:
                foilName = f.readline().strip().replace(' ', '/_/')

            if foilName == self.rootName:
                points = pd.read_csv(path, delim_whitespace = True, header = None, skiprows = 1).astype(float)
                x = points.to_numpy()[:, 0]
                y = np.zeros(len(x))
                z = points.to_numpy()[:, 1]
                self.root = Airfoil(np.array([x, y, z]).T, foilName)

            if foilName == self.tipName:
                points = pd.read_csv(path, delim_whitespace = True, header = None, skiprows = 1).astype(float)
                x = points.to_numpy()[:, 0]
                y = np.zeros(len(x))
                z = points.to_numpy()[:, 1]
                self.tip = Airfoil(np.array([x, y, z]).T, foilName)
        self.root.refine(self.npoints)
        self.tip.refine(self.npoints)
        self.root.update_ofoil()
        self.tip.update_ofoil()
        return [self.root, self.tip]

    def set_chord(self, a, b):
        self.chord = [a, b]

    def set_span(self, a, b):
        self.span = [a, b]

    def set_sweep(self, a, b):
        self.sweep = [a, b]

    def set_twist(self, a, b):
        self.twist = [a, b]

    def set_dihedral(self, a, b):
        self.dihedral = [a, b]

    def set_qcpoint(self, a, b):
        self.root.set_qcpoint(a)
        self.tip.set_qcpoint(b)

    def set_offset(self, a, b, c):
        self.zOffsetRoot = a
        self.yOffsetRoot = b
        self.xOffsetRoot = c

    def get_chord(self):
        return self.chord

    def get_span(self):
        return self.span

    def get_sweep(self):
        return self.sweep

    def get_twist(self):
        return self.twist

    def get_dihedral(self):
        return self.dihedral

    def get_foils(self):
        return self.root.foil, self.tip.foil

    def get_qcpoint(self):
        return self.root.get_qcpoint(), self.tip.get_qcpoint()

    '''
    The build function takes the two airfoils and moves them to the correct positions
    specified by the user to form the required wing.
    '''
    def build(self):
        # Refining the profiles.
        #self.root.refine(self.npoints)
        #self.tip.refine(self.npoints)

        # Scaling the profiles to the correct chord length.
        self.root.scale(self.chord[0])
        self.tip.scale(self.chord[1])

        # Rotating the profiles to allow for twist.
        rootCenter = deepcopy(self.root.get_qcpoint())
        tipCenter = deepcopy(self.tip.get_qcpoint())
        self.root.translate(rootCenter, -1)
        self.tip.translate(tipCenter, -1)
        self.root.rotate(yAxis, self.twist[0])
        self.tip.rotate(yAxis, self.twist[1])
        self.root.translate(rootCenter, 1)
        self.tip.translate(tipCenter, 1)

        # Adding the y-coordinate for span.
        self.root.translate(yAxis, self.span[0])
        self.tip.translate(yAxis, self.span[1])

        # Translating both airfoils for wing sweep.
        self.root.translate(xAxis, self.sweep[0])
        self.tip.translate(xAxis, self.sweep[1])

        # Rotating both foils for dihedral.
        self.root.rotate(xAxis, self.dihedral[0])
        self.tip.rotate(xAxis, self.dihedral[1])


    '''
    The allign_le and allign_qc functions rotate the section so the leading edge (le)
    or the rotation point (qc) are parallel to the y axis. This function allows wings
    with high sweep to be made on small machines and to minimize the amount of wasted
    foam.
    '''
    def allign_le(self):
        # Find the angle of the leading edge
        xOffset = self.root.get_lepoint()[0] - self.tip.get_lepoint()[0]
        span = np.abs(self.span[0] - self.span[1])
        alpha = math.atan2(-xOffset, span)

        # Rotate the entire wing section build counterclockwise by angle alpha.
        self.root.rotate(zAxis, alpha)
        self.tip.rotate(zAxis, alpha)

    def allign_qc(self):
        # Find the angle of the quarter chord line
        xOffset = self.root.get_qcpoint()[0] - self.tip.get_qcpoint()[0]
        span = np.abs(self.span[0] - self.span[1])
        alpha = math.atan2(-xOffset, span)

        # Rotate the entire wing section build counterclockwise by angle alpha.
        self.root.rotate(zAxis, alpha)
        self.tip.rotate(zAxis, alpha)

    '''
    This function translates the wing so that it is located in a user specified positions
    '''
    def locate_section(self):
        # Translating both airfoils for the root offset.
        translationVector = xAxis* self.xOffsetRoot + yAxis* self.yOffsetRoot + zAxis*self.zOffsetRoot
        self.root.translate(translationVector, 1)
        self.tip.translate(translationVector, 1)


'''
This class is responisble to convert the section profiles to cutting profiles and
to gcode. This class does depend on machine properties.
'''
class Profile:

    def __init__(self, Sec):

        self.Sec = Sec  # Must be an instance of Section

        self.ySpan = 1000 # Distance between 2d movement platforms in the y direction.

        self.rootCut = None
        self.tipCut = None

        self.meshPoints = 100   # Number of points in y direction mesh

    def set_yspan(self, ySpan):
        self.ySpan = ySpan

    def get_yspan(self):
        return self.ySpan

    def project(self, plane):
        # This function find the projected shapes intersecting with the cutting planes.
        # This is achieved by drawing a straign line throuhg the n-th point on both the
        # tip and root foil and finding the intersection of that line with the cutting planes.

        # Get airfoil coordinates
        rootFoil, tipFoil = self.Sec.get_foils()

        # Find directional ratios
        directionalRat = tipFoil - rootFoil

        # Intersection with cutting planes y
        constants = (plane - rootFoil[:, 1])/directionalRat[:, 1]

        # X coordinates
        xProjection = constants * directionalRat[:, 0] + rootFoil[:, 0]

        # Z coordinates
        zProjection = constants * directionalRat[:, 2] + rootFoil[:, 2]

        # Y coordinates
        y = np.zeros(len(zProjection))+plane

        # Store the coordinates in two numpy arrays
        return np.array([xProjection, y, zProjection]).T

    def cutting_planes(self):
        self.rootCut = self.project(0)
        self.tipCut = self.project(self.ySpan)

    def get_profiles(self):
        return self.rootCut, self.tipCut
