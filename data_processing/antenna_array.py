"""
Antenna Array Class for mmWave Applications

This module provides a Python implementation of an antenna array class
for modeling uniform linear arrays (ULA) and uniform planar arrays (UPA).
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from copy import deepcopy


def rotate_cartesian_point(x, y, z, rot_x, rot_y, rot_z):
    """
    Rotate a 3D point using Euler angles.
    
    Args:
        x, y, z: Coordinates of the point
        rot_x, rot_y, rot_z: Rotation angles around x, y, z axes (radians)
        
    Returns:
        u, v, w: Rotated coordinates
    """
    # Rotation matrix around x-axis
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(rot_x), -np.sin(rot_x)],
                   [0, np.sin(rot_x), np.cos(rot_x)]])
    
    # Rotation matrix around y-axis
    Ry = np.array([[np.cos(rot_y), 0, np.sin(rot_y)],
                   [0, 1, 0],
                   [-np.sin(rot_y), 0, np.cos(rot_y)]])
    
    # Rotation matrix around z-axis
    Rz = np.array([[np.cos(rot_z), -np.sin(rot_z), 0],
                   [np.sin(rot_z), np.cos(rot_z), 0],
                   [0, 0, 1]])
    
    # Combined rotation
    R = Rz @ Ry @ Rx
    point = np.array([x, y, z])
    rotated = R @ point
    
    return rotated[0], rotated[1], rotated[2]


class AntennaArray:
    """
    Antenna Array class for modeling and analyzing antenna arrays.
    
    Attributes:
        num_antennas (int): Number of antenna elements in array
        x (np.ndarray): x coordinates of array elements (in wavelengths)
        y (np.ndarray): y coordinates of array elements (in wavelengths)
        z (np.ndarray): z coordinates of array elements (in wavelengths)
        weights (np.ndarray): Element weights (complex)
        marker (str): Element marker when plotting
        element_gain_dB (float): Element gain in dB
        element_gain_linear (float): Element gain (linear scale)
    """
    
    def __init__(self, N=None, M=None, plane='xz'):
        """
        Creates an instance of an antenna array object.
        
        Args:
            N: (optional) number of elements in the array; or number of
               rows in a planar array if M is passed
            M: (optional) number of columns in a planar array
            plane: (optional) a string specifying the plane to create
                   the planar array in (either 'xz', 'xy', or 'yz'); 
                   default is 'xz'
        
        Notes:
            - AntennaArray() creates an empty array object.
            - AntennaArray(N) creates an array object where N array elements 
              are uniformly spaced one-half wavelength apart along the x-axis.
            - AntennaArray(N, M) creates a uniform planar array with N rows 
              and M columns, uniformly spaced one-half wavelength apart 
              in the x-z plane.
        """
        self.num_antennas = 0
        self.x = np.array([])
        self.y = np.array([])
        self.z = np.array([])
        self.weights = np.array([])
        self.marker = 'kx'
        self.element_gain_dB = 0
        self.element_gain_linear = 1
        self.ep = 1  # Element pattern (placeholder)
        
        if N is None:
            # Create empty array
            self.reset()
        elif M is None:
            # Create ULA
            self.initialize_ula(N)
        elif isinstance(M, str):
            # Create ULA along specific axis
            self.initialize_ula(N, M)
        else:
            # Create UPA
            self.initialize_upa(N, M, plane)
    
    @classmethod
    def create(cls, N=None, M=None, plane='xz'):
        """
        Creates an antenna array object (alternative constructor).
        
        Args:
            N: (optional) number of elements or number of rows
            M: (optional) axis string or number of columns
            plane: (optional) plane specifier for UPA ('xz', 'xy', or 'yz')
            
        Returns:
            obj: An AntennaArray object
        """
        return cls(N, M, plane)
    
    def copy(self):
        """Create a deep copy of the array."""
        return deepcopy(self)
    
    # -----------------------------------------------------------------
    # Setup functions
    # -----------------------------------------------------------------
    
    def reset(self):
        """Removes all array elements from the array."""
        self.x = np.array([])
        self.y = np.array([])
        self.z = np.array([])
        self.weights = np.array([])
        self.num_antennas = 0
        self.set_marker('kx')
    
    def initialize_ula(self, N, ax='x'):
        """
        Resets the array and creates a half-wavelength spaced, 
        uniform linear array along a desired axis.
        
        Args:
            N: The number of array elements
            ax: (optional) axis to create ULA along ('x', 'y', or 'z'); 
                default is 'x'
        """
        self.reset()
        n = np.arange(N) / 2
        xx = np.zeros(N)
        yy = np.zeros(N)
        zz = np.zeros(N)
        
        if ax.lower() == 'x':
            xx = n
        elif ax.lower() == 'y':
            yy = n
        elif ax.lower() == 'z':
            zz = n
        else:
            raise ValueError('Invalid axis specifier (x, y, or z). Cannot create ULA.')
        
        self.add_element(xx, yy, zz)
        self.translate()  # Center at origin
    
    def initialize_upa(self, nrows, ncols=None, plane='xz'):
        """
        Resets the array and creates a half-wavelength spaced, 
        uniform planar array in a desired plane.
        
        Args:
            nrows: Number of rows in the planar array
            ncols: (optional) Number of columns; if None, uses nrows
            plane: (optional) Plane to create UPA in ('xy', 'xz', or 'yz'); 
                   default is 'xz'
        """
        if ncols is None:
            ncols = nrows
        
        self.reset()
        m = np.arange(nrows) / 2
        n = np.arange(ncols) / 2
        N = nrows * ncols
        
        if plane.lower() == 'xz':
            xx = np.repeat(n, nrows)
            yy = np.zeros(N)
            zz = np.tile(m, ncols)
        elif plane.lower() == 'xy':
            xx = np.repeat(n, nrows)
            yy = np.tile(m, ncols)
            zz = np.zeros(N)
        elif plane.lower() == 'yz':
            xx = np.zeros(N)
            yy = np.repeat(n, nrows)
            zz = np.tile(m, ncols)
        else:
            raise ValueError('Invalid plane specifier. Cannot create UPA.')
        
        self.add_element(xx, yy, zz)
        self.translate()  # Center at origin
    
    # -----------------------------------------------------------------
    # Set functions
    # -----------------------------------------------------------------
    
    def set_marker(self, marker='kx'):
        """
        Sets the marker used when plotting the array elements.
        
        Args:
            marker: (optional) Plot marker to use; 'transmit' or 'receive' 
                    are also valid; default is 'kx'
        """
        if marker.lower() == 'transmit':
            marker = 'bx'  # Blue x for transmit arrays
        elif marker.lower() == 'receive':
            marker = 'r+'  # Red + for receive arrays
        
        self.marker = marker
    
    def set_weights(self, w=None):
        """
        Applies complex weights to each array element.
        
        Args:
            w: (optional) Weight vector where the i-th array element is 
               weighted by the i-th element in w; if None, uses ones
        """
        if w is None:
            w = np.ones(self.num_antennas)
        
        w = np.array(w).flatten()  # Force 1D array
        
        if len(w) == self.num_antennas:
            self.weights = w
        else:
            print('Warning: Number of weights should equal number of array elements.')
            print('Not setting array weights.')
    
    def set_element_gain(self, power_gain_dB):
        """
        Sets the gain of each element in the array.
        
        Args:
            power_gain_dB: The element's power gain in dB
        """
        self.element_gain_dB = power_gain_dB
        self.element_gain_linear = 10 ** (power_gain_dB / 20)
    
    # -----------------------------------------------------------------
    # Modifying functions
    # -----------------------------------------------------------------
    
    def add_element(self, x, y, z):
        """
        Adds an element or group of elements to the array.
        
        Args:
            x: Scalar or array of element x-coordinate(s) (in wavelengths)
            y: Scalar or array of element y-coordinate(s) (in wavelengths)
            z: Scalar or array of element z-coordinate(s) (in wavelengths)
        """
        x = np.atleast_1d(x).flatten()
        y = np.atleast_1d(y).flatten()
        z = np.atleast_1d(z).flatten()
        
        if len(x) == len(y) == len(z):
            self.x = np.concatenate([self.x, x])
            self.y = np.concatenate([self.y, y])
            self.z = np.concatenate([self.z, z])
            self.num_antennas = len(self.x)
            self.weights = np.ones(self.num_antennas)
        else:
            raise ValueError('x, y, and z must be the same length.')
    
    def remove_element(self, idx=None):
        """
        Removes an element from the array.
        
        Args:
            idx: (optional) Index of element to remove; if None, removes last element
        """
        if idx is None:
            idx = self.num_antennas - 1
        else:
            if idx >= self.num_antennas:
                raise ValueError('Element index must be less than number of elements.')
            elif idx < 0:
                raise ValueError('Element index must be at least 0.')
        
        self.x = np.delete(self.x, idx)
        self.y = np.delete(self.y, idx)
        self.z = np.delete(self.z, idx)
        self.num_antennas -= 1
        self.weights = np.ones(self.num_antennas)
    
    def translate(self, x=None, y=None, z=None):
        """
        Shifts the location of all elements in the array.
        When x, y, z are None, centers the array at the origin.
        
        Args:
            x: (optional) Wavelengths to move in x direction
            y: (optional) Wavelengths to move in y direction
            z: (optional) Wavelengths to move in z direction
        """
        if x is None:
            x = -np.mean(self.x) if len(self.x) > 0 else 0
        if y is None:
            y = -np.mean(self.y) if len(self.y) > 0 else 0
        if z is None:
            z = -np.mean(self.z) if len(self.z) > 0 else 0
        
        self.x += x
        self.y += y
        self.z += z
    
    def rotate(self, rot_x=0, rot_y=0, rot_z=0, inplace=False):
        """
        Rotates the array in 3D space.
        
        Args:
            rot_x: Rotation around x-axis (radians)
            rot_y: (optional) Rotation around y-axis (radians)
            rot_z: (optional) Rotation around z-axis (radians)
            inplace: (optional) If True, rotate about array's center; 
                     if False, rotate about origin
        """
        if inplace:
            x_mean = np.mean(self.x)
            y_mean = np.mean(self.y)
            z_mean = np.mean(self.z)
            self.translate()  # Shift to origin
        
        for i in range(self.num_antennas):
            u, v, w = rotate_cartesian_point(
                self.x[i], self.y[i], self.z[i], 
                rot_x, rot_y, rot_z
            )
            self.x[i] = u
            self.y[i] = v
            self.z[i] = w
        
        if inplace:
            self.translate(x_mean, y_mean, z_mean)  # Shift back
    
    def translate_array(self, x, y, z):
        """Alias for translate method."""
        self.translate(x, y, z)
    
    # -----------------------------------------------------------------
    # Get functions
    # -----------------------------------------------------------------
    
    def get_array_response(self, az=0, el=0):
        """
        Returns the array response vector at given azimuth and elevation.
        
        Args:
            az: (optional) Azimuth angle(s) (radians); default is 0
            el: (optional) Elevation angle(s) (radians); default is 0
            
        Returns:
            a: Array response vector(s)
        """
        az = np.atleast_1d(az)
        el = np.atleast_1d(el)
        
        # Distances relative to first element
        dx = self.x - self.x[0]
        dy = self.y - self.y[0]
        dz = self.z - self.z[0]
        
        # Reshape for broadcasting
        dx = dx[:, np.newaxis]
        dy = dy[:, np.newaxis]
        dz = dz[:, np.newaxis]
        
        # Calculate phase shifts
        phase = 2 * np.pi * (
            dx * np.sin(az) * np.cos(el) +
            dy * np.cos(az) * np.cos(el) +
            dz * np.sin(el)
        )
        
        a = np.exp(1j * phase)
        
        # Return as 1D if single angle, otherwise 2D
        if a.shape[1] == 1:
            return a.flatten()
        return a
    
    def get_array_gain(self, az=0, el=0):
        """
        Returns the array gain in a given direction with current weights.
        
        Args:
            az: (optional) Azimuth angle(s) (radians); default is 0
            el: (optional) Elevation angle(s) (radians); default is 0
            
        Returns:
            g: Complex gain of the weighted array
        """
        a = self.get_array_response(az, el)
        w = self.weights
        
        if a.ndim == 1:
            g = np.dot(w, a)
        else:
            g = np.dot(w, a)
        
        return g
    
    def get_largest_dimension(self):
        """Returns the largest dimension of the array."""
        X = self.x[:, np.newaxis] - self.x[np.newaxis, :]
        Y = self.y[:, np.newaxis] - self.y[np.newaxis, :]
        Z = self.z[:, np.newaxis] - self.z[np.newaxis, :]
        R = np.sqrt(X**2 + Y**2 + Z**2)
        return np.max(R)
    
    def get_weighted_array_response(self, az=0, el=0):
        """
        Returns the weighted array response vector.
        
        Args:
            az: (optional) Azimuth angle(s) (radians); default is 0
            el: (optional) Elevation angle(s) (radians); default is 0
            
        Returns:
            a: Weighted array response vector
        """
        v = self.get_array_response(az, el)
        w = self.weights
        
        if v.ndim == 1:
            a = v * w
        else:
            a = v * w[:, np.newaxis]
        
        return a
    
    def get_conjugate_beamformer(self, az=0, el=0):
        """
        Returns conjugate beamforming weights for steering.
        
        Args:
            az: (optional) Azimuth angle(s) (radians); default is 0
            el: (optional) Elevation angle(s) (radians); default is 0
            
        Returns:
            w: Conjugate beamforming weights
        """
        a = self.get_array_response(az, el)
        w = np.conj(a)
        return w
    
    def get_conjugate_beamformer_azimuth_matrix(self, N=None, el=0):
        """
        Returns matrix of conjugate beamformers in azimuth directions.
        
        Args:
            N: Number of beamformers (columns); default is num_antennas
            el: Elevation angle (radians); default is 0
            
        Returns:
            A: Matrix of beamformers (num_antennas x N)
            th: Corresponding azimuth angles
        """
        if N is None:
            N = self.num_antennas
        
        th = np.linspace(-np.pi, np.pi, N, endpoint=False)
        A = np.zeros((self.num_antennas, N), dtype=complex)
        
        for i in range(N):
            w = self.get_array_response(th[i], el)
            A[:, i] = w
        
        return A, th
    
    def get_zero_forcing_beamformer(self, az_des, el_des, az_int, el_int):
        """
        Returns zero-forcing beamformer that accepts energy in desired
        directions and rejects energy in interfering directions.
        
        Args:
            az_des: Desired azimuth angle(s) (radians)
            el_des: Desired elevation angle(s) (radians)
            az_int: Interfering azimuth angle(s) (radians)
            el_int: Interfering elevation angle(s) (radians)
            
        Returns:
            w: Zero-forcing beamformer weights
        """
        az_des = np.atleast_1d(az_des)
        el_des = np.atleast_1d(el_des)
        az_int = np.atleast_1d(az_int)
        el_int = np.atleast_1d(el_int)
        
        num_des = len(az_des)
        num_int = len(az_int)
        
        # Build desired channel
        H_des = np.zeros(self.num_antennas, dtype=complex)
        for i in range(num_des):
            h = self.get_array_response(az_des[i], el_des[i])
            H_des += h
        
        # Build interfering channel
        H_int = np.zeros(self.num_antennas, dtype=complex)
        for i in range(num_int):
            h = self.get_array_response(az_int[i], el_int[i])
            H_int += h
        
        # Zero-forcing solution
        H = np.column_stack([H_des, H_int])
        w = np.linalg.pinv(H)
        w = w[0, :]  # First row corresponds to desired direction
        w = self.num_antennas * w  # Scale to match conjugate BF gain
        
        return w
    
    def get_near_field_response(self, freq, x, y, z=0):
        """
        Returns near-field array response.
        
        Args:
            freq: Frequency (Hz)
            x, y: Target coordinates (meters)
            z: (optional) Target z-coordinate (meters); default is 0
            
        Returns:
            v: Near-field response vector
        """
        lambda_m = 3e8 / freq
        dx = self.x - x / lambda_m
        dy = self.y - y / lambda_m
        dz = self.z - z / lambda_m
        r = np.sqrt(dx**2 + dy**2 + dz**2)  # In wavelengths
        
        v = (1.0 / r) * (1.0 / lambda_m) * np.exp(-1j * 2 * np.pi * r)
        v = v / np.linalg.norm(v) * np.sqrt(self.num_antennas)
        
        return v
    
    def get_near_field_response_v2(self, freq, x, y, z, d, eta, nu):
        """
        Returns near-field array response (version 2 with parameters).
        
        Args:
            freq: Frequency (Hz)
            x, y, z: Target coordinates (meters)
            d: Distance parameter
            eta: Phase scaling factor
            nu: Power law exponent
            
        Returns:
            v: Near-field response vector
        """
        lambda_m = 3e8 / freq
        dx = self.x - x / lambda_m
        dy = self.y - y / lambda_m
        dz = self.z - z / lambda_m
        r = np.sqrt(dx**2 + dy**2 + dz**2) * lambda_m  # In meters
        
        v = (1.0 / r**nu) * np.exp(-1j * 2 * np.pi / lambda_m * r * eta)
        v = v / np.linalg.norm(v) * np.sqrt(self.num_antennas)
        
        return v
    
    def get_array_pattern_azimuth(self, el=0, N=1024, full=False):
        """
        Returns weighted array pattern as function of azimuth.
        
        Args:
            el: (optional) Elevation angle (radians); default is 0
            N: (optional) Number of azimuth points; default is 1024
            full: (optional) If True, sweep [-π, π); if False, [-π/2, π/2)
            
        Returns:
            x: Array pattern vs azimuth
            az: Azimuth angles (radians)
            el: Elevation angle used
        """
        if full:
            th_start = -np.pi
            th_stop = np.pi
        else:
            th_start = -np.pi / 2
            th_stop = np.pi / 2
        
        az = np.linspace(th_start, th_stop, N, endpoint=False)
        x = np.zeros(N, dtype=complex)
        
        for i in range(N):
            x[i] = self.get_array_gain(az[i], el)
        
        return x, az, el
    
    def get_array_pattern_elevation(self, az=0, N=1024, full=False):
        """
        Returns weighted array pattern as function of elevation.
        
        Args:
            az: (optional) Azimuth angle (radians); default is 0
            N: (optional) Number of elevation points; default is 1024
            full: (optional) If True, sweep [-π, π); if False, [-π/2, π/2)
            
        Returns:
            x: Array pattern vs elevation
            el: Elevation angles (radians)
            az: Azimuth angle used
        """
        if full:
            th_start = -np.pi
            th_stop = np.pi
        else:
            th_start = -np.pi / 2
            th_stop = np.pi / 2
        
        el = np.linspace(th_start, th_stop, N, endpoint=False)
        x = np.zeros(N, dtype=complex)
        
        for i in range(N):
            x[i] = self.get_array_gain(az, el[i])
        
        return x, el, az
    
    def get_array_center(self):
        """
        Returns the center of the array (in wavelengths).
        
        Returns:
            xyz: Array center [x, y, z]
        """
        mean_x = np.mean(self.x) if len(self.x) > 0 else 0
        mean_y = np.mean(self.y) if len(self.y) > 0 else 0
        mean_z = np.mean(self.z) if len(self.z) > 0 else 0
        return np.array([mean_x, mean_y, mean_z])
    
    def get_element_pattern_azimuth(self):
        """Returns element pattern as function of azimuth (placeholder)."""
        return self.ep, 1
    
    def get_element_pattern_elevation(self):
        """Returns element pattern as function of elevation (placeholder)."""
        return self.ep, 1
    
    # -----------------------------------------------------------------
    # Show/Plotting functions
    # -----------------------------------------------------------------
    
    def show_beamformer_pattern(self, w):
        """
        Plots beam pattern with specific beamforming weights.
        
        Args:
            w: Vector of complex beamforming weights
        """
        w = np.array(w).flatten()
        orig_weights = self.weights.copy()
        self.set_weights(w)
        self.show_array_pattern()
        self.set_weights(orig_weights)
    
    def show_beamformer_pattern_magnitude(self, w):
        """
        Plots beam pattern magnitude with specific weights.
        
        Args:
            w: Vector of complex beamforming weights
        """
        w = np.array(w).flatten()
        orig_weights = self.weights.copy()
        self.set_weights(w)
        self.show_array_pattern_magnitude()
        self.set_weights(orig_weights)
    
    def show_array_pattern(self, az=0, el=0, N=1024, full=False, loglin='dB'):
        """
        Plots array pattern vs azimuth and elevation.
        
        Args:
            az: (optional) Azimuth for elevation pattern (radians)
            el: (optional) Elevation for azimuth pattern (radians)
            N: (optional) Number of points; default is 1024
            full: (optional) Full sweep (True) or half (False)
            loglin: (optional) 'dB' or 'lin'; default is 'dB'
        """
        # Azimuth pattern
        xx, th, el_used = self.get_array_pattern_azimuth(el, N, full)
        
        if loglin.lower() == 'db':
            x_mag = 20 * np.log10(np.abs(xx) + 1e-12)
            maglabel = 'Magnitude (dB)'
        else:
            x_mag = np.abs(xx)
            maglabel = 'Linear Magnitude'
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Azimuth magnitude
        axes[0, 0].plot(th * 180 / np.pi, x_mag, 'k-')
        axes[0, 0].grid(True)
        axes[0, 0].set_xlabel('Azimuth (deg.)')
        axes[0, 0].set_ylabel(maglabel)
        axes[0, 0].set_title(f'Elevation of {el_used * 180 / np.pi:.1f} deg.')
        
        # Azimuth phase
        axes[1, 0].plot(th * 180 / np.pi, np.angle(xx), 'k-')
        axes[1, 0].grid(True)
        axes[1, 0].set_xlabel('Azimuth (deg.)')
        axes[1, 0].set_ylabel('Phase (rad.)')
        
        # Elevation pattern
        xx, ph, az_used = self.get_array_pattern_elevation(az, N, full)
        
        if loglin.lower() == 'db':
            x_mag = 20 * np.log10(np.abs(xx) + 1e-12)
        else:
            x_mag = np.abs(xx)
        
        # Elevation magnitude
        axes[0, 1].plot(ph * 180 / np.pi, x_mag, 'k-')
        axes[0, 1].grid(True)
        axes[0, 1].set_xlabel('Elevation (deg.)')
        axes[0, 1].set_ylabel(maglabel)
        axes[0, 1].set_title(f'Azimuth of {az_used * 180 / np.pi:.1f} deg.')
        
        # Elevation phase
        axes[1, 1].plot(ph * 180 / np.pi, np.angle(xx), 'k-')
        axes[1, 1].grid(True)
        axes[1, 1].set_xlabel('Elevation (deg.)')
        axes[1, 1].set_ylabel('Phase (rad.)')
        
        plt.tight_layout()
        plt.show()
    
    def show_array_pattern_magnitude(self, az=0, el=0, N=1024, full=False, loglin='dB'):
        """
        Plots array pattern magnitude vs azimuth.
        
        Args:
            az: (optional) Azimuth for elevation pattern (radians)
            el: (optional) Elevation for azimuth pattern (radians)
            N: (optional) Number of points; default is 1024
            full: (optional) Full sweep (True) or half (False)
            loglin: (optional) 'dB' or 'lin'; default is 'dB'
        """
        xx, th, el_used = self.get_array_pattern_azimuth(el, N, full)
        
        if loglin.lower() == 'db':
            x = 20 * np.log10(np.abs(xx) + 1e-12)
            maglabel = 'Magnitude (dB)'
        else:
            x = np.abs(xx)
            maglabel = 'Linear Magnitude'
        
        plt.figure(figsize=(10, 6))
        plt.plot(th * 180 / np.pi, x, 'k-')
        plt.grid(True)
        plt.xlabel('Azimuth (deg.)')
        plt.ylabel(maglabel)
        plt.title(f'Elevation of {el_used * 180 / np.pi:.1f} deg.')
        plt.tight_layout()
        plt.show()
    
    def show_array_pattern_azimuth(self, ax=None, el=0, N=1024, full=False):
        """
        Plots magnitude of array pattern vs azimuth.
        
        Args:
            ax: (optional) Matplotlib axes handle
            el: (optional) Elevation angle (radians)
            N: (optional) Number of points
            full: (optional) Full sweep (True) or half (False)
            
        Returns:
            ax: Axes handle
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        xx, th, el_used = self.get_array_pattern_azimuth(el, N, full)
        
        ax.plot(th * 180 / np.pi, np.abs(xx), 'k-')
        ax.grid(True)
        ax.set_xlabel('Azimuth (deg.)')
        ax.set_ylabel('Linear Magnitude')
        ax.set_title(f'Elevation of {el_used * 180 / np.pi:.1f} deg.')
        
        return ax
    
    def show_array_pattern_elevation(self, ax=None, az=0, N=1024, full=False):
        """
        Plots magnitude of array pattern vs elevation.
        
        Args:
            ax: (optional) Matplotlib axes handle
            az: (optional) Azimuth angle (radians)
            N: (optional) Number of points
            full: (optional) Full sweep (True) or half (False)
            
        Returns:
            ax: Axes handle
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        xx, ph, az_used = self.get_array_pattern_elevation(az, N, full)
        
        ax.plot(ph * 180 / np.pi, np.abs(xx), 'k-')
        ax.grid(True)
        ax.set_xlabel('Elevation (deg.)')
        ax.set_ylabel('Linear Magnitude')
        ax.set_title(f'Azimuth of {az_used * 180 / np.pi:.1f} deg.')
        
        return ax
    
    def show_polar_array_pattern_azimuth(self, ax=None, el=0, N=1024, full=False):
        """
        Plots azimuth array pattern in polar plot.
        
        Args:
            ax: (optional) Matplotlib polar axes handle
            el: (optional) Elevation angle (radians)
            N: (optional) Number of points
            full: (optional) Full sweep (True) or half (False)
            
        Returns:
            ax: Polar axes handle
        """
        if ax is None:
            fig = plt.figure(figsize=(8, 8))
            ax = fig.add_subplot(111, projection='polar')
        
        x, th, el_used = self.get_array_pattern_azimuth(el, N, full)
        
        ax.plot(th, np.abs(x), 'k-')
        ax.set_theta_direction(-1)
        ax.set_theta_zero_location('N')
        ax.set_title(f'Elevation of {el_used * 180 / np.pi:.1f} deg.', pad=20)
        
        return ax
    
    def show_polar_array_pattern_elevation(self, ax=None, az=0, N=1024, full=False):
        """
        Plots elevation array pattern in polar plot.
        
        Args:
            ax: (optional) Matplotlib polar axes handle
            az: (optional) Azimuth angle (radians)
            N: (optional) Number of points
            full: (optional) Full sweep (True) or half (False)
            
        Returns:
            ax: Polar axes handle
        """
        if ax is None:
            fig = plt.figure(figsize=(8, 8))
            ax = fig.add_subplot(111, projection='polar')
        
        x, ph, az_used = self.get_array_pattern_elevation(az, N, full)
        
        ax.plot(ph, np.abs(x), 'k-')
        ax.set_theta_direction(-1)
        ax.set_theta_zero_location('N')
        ax.set_title(f'Azimuth of {az_used * 180 / np.pi:.1f} deg.', pad=20)
        
        return ax
    
    def show_radiation_pattern(self, ax=None, res='medium', full=True):
        """
        Plots array gain in 3D.
        
        Args:
            ax: (optional) Matplotlib 3D axes handle
            res: (optional) Resolution: 'low', 'medium', or 'high'
            full: (optional) Full sweep (True) or half (False)
            
        Returns:
            ax: 3D axes handle
        """
        if ax is None:
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
        
        if res.lower() in ['low', 'lo']:
            num_az, num_el = 180, 90
        elif res.lower() in ['high', 'hi']:
            num_az, num_el = 720, 360
        else:  # medium
            num_az, num_el = 360, 180
        
        if full:
            lower_az, upper_az = -np.pi, np.pi
        else:
            lower_az, upper_az = -np.pi/2, np.pi/2
        
        AoA_ele_rad = np.linspace(-np.pi/2, np.pi/2, num_el)
        AoA_azi_rad = np.linspace(lower_az, upper_az, num_az)
        
        G = np.zeros((num_az, num_el))
        
        for idx_el in range(num_el):
            v = self.get_array_gain(AoA_azi_rad, AoA_ele_rad[idx_el])
            G[:, idx_el] = np.abs(v)
        
        AoA_ele_grid, AoA_azi_grid = np.meshgrid(AoA_ele_rad, AoA_azi_rad)
        
        # Convert to Cartesian
        y = G * np.cos(AoA_azi_grid) * np.cos(AoA_ele_grid)
        x = G * np.sin(AoA_azi_grid) * np.cos(AoA_ele_grid)
        z = G * np.sin(AoA_ele_grid)
        
        surf = ax.plot_surface(x, y, z, cmap=cm.viridis,
                               facecolors=cm.viridis(G/G.max()),
                               linewidth=0, antialiased=True)
        
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')
        ax.set_box_aspect([1, 1, 1])
        plt.colorbar(surf, ax=ax, shrink=0.5)
        
        return ax
    
    def show_beam_codebook_3d(self, F):
        """
        Plots 3D beam codebook.
        
        Args:
            F: Matrix of beamforming vectors (columns are beams)
        """
        AoA_ele_rad = np.linspace(-np.pi/2, np.pi/2, 180)
        AoA_azi_rad = np.linspace(-np.pi/2, np.pi/2, 180)
        AoA_ele_grid, AoA_azi_grid = np.meshgrid(AoA_ele_rad, AoA_azi_rad)
        
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        for index in range(F.shape[1]):
            AF = np.zeros(AoA_ele_grid.shape)
            
            for ele in range(AoA_ele_grid.shape[0]):
                for azi in range(AoA_azi_grid.shape[1]):
                    v = self.get_array_response(
                        AoA_azi_grid[ele, azi], 
                        AoA_ele_grid[ele, azi]
                    )
                    f = F[:, index]
                    AF[ele, azi] = np.abs(np.dot(v, f))**2
            
            # Convert to Cartesian
            y = AF * np.cos(AoA_azi_grid) * np.cos(AoA_ele_grid)
            x = AF * np.sin(AoA_azi_grid) * np.cos(AoA_ele_grid)
            z = AF * np.sin(AoA_ele_grid)
            
            ax.plot_surface(x, y, z, cmap=cm.viridis, alpha=0.3)
        
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_zlabel('z')
        plt.show()
    
    def show_beam_codebook_azimuth(self, W, el=0, N=1024, full=False):
        """
        Plots beam codebook in azimuth (polar).
        
        Args:
            W: Matrix of beamforming weights (columns are beams)
            el: (optional) Elevation angle (radians)
            N: (optional) Number of points
            full: (optional) Full sweep (True) or half (False)
        """
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='polar')
        
        weights_orig = self.weights.copy()
        
        for idx_beam in range(W.shape[1]):
            self.set_weights(W[:, idx_beam])
            x, th, el_used = self.get_array_pattern_azimuth(el, N, full)
            ax.plot(th, np.abs(x))
        
        self.set_weights(weights_orig)
        
        ax.set_theta_direction(-1)
        ax.set_theta_zero_location('N')
        ax.set_title(f'Elevation of {el * 180 / np.pi:.1f} deg.', pad=20)
        plt.show()
    
    def show_element_pattern(self):
        """Plots element pattern (placeholder)."""
        print("Element pattern visualization not fully implemented.")
        print("Element gain: {:.2f} dB".format(self.element_gain_dB))
    
    def show_2d(self, ax=None, plane='xz'):
        """
        Plots array elements in 2D.
        
        Args:
            ax: (optional) Matplotlib axes handle
            plane: (optional) Plane to show: 'xy', 'xz', or 'yz'
            
        Returns:
            fig, ax: Figure and axes handles
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        else:
            fig = ax.get_figure()
        
        if plane.lower() == 'xy':
            xx, yy = self.x, self.y
        elif plane.lower() == 'xz':
            xx, yy = self.x, self.z
        elif plane.lower() == 'yz':
            xx, yy = self.y, self.z
        else:
            raise ValueError('Invalid plane specifier.')
        
        ax.plot(xx, yy, self.marker)
        ax.grid(True)
        ax.set_xlabel(f'{plane[0]} (in λ)')
        ax.set_ylabel(f'{plane[1]} (in λ)')
        ax.set_aspect('equal')
        
        return fig, ax
    
    def show_3d(self, ax=None):
        """
        Plots array elements in 3D.
        
        Args:
            ax: (optional) Matplotlib 3D axes handle
            
        Returns:
            fig, ax: Figure and axes handles
        """
        if ax is None:
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
        else:
            fig = ax.get_figure()
        
        ax.scatter(self.x, self.y, self.z, marker='o', s=50, c='k')
        ax.grid(True)
        ax.set_xlabel('x (in λ)')
        ax.set_ylabel('y (in λ)')
        ax.set_zlabel('z (in λ)')
        ax.set_box_aspect([1, 1, 1])
        
        return fig, ax
    
    def __repr__(self):
        """String representation of the array."""
        return (f"AntennaArray(num_antennas={self.num_antennas}, "
                f"center={self.get_array_center()})")

