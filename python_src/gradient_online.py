# In order to launch execute:
# python3 gradient_online.py

import numpy as np
from numpy.linalg import norm
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.ndimage.morphology import distance_transform_edt as bwdist
from math import *

from progress.bar import FillingCirclesBar
from tasks import get_movie_writer
from tasks import get_dummy_context_mgr



def draw_map(R_obstacles, nrows=500, ncols=500):
    skip = 10
    [x_m, y_m] = np.meshgrid(np.linspace(-2.5, 2.5, ncols), np.linspace(-2.5, 2.5, nrows))
    [gy, gx] = np.gradient(-f);
    Q = plt.quiver(x_m[::skip, ::skip], y_m[::skip, ::skip], gx[::skip, ::skip], gy[::skip, ::skip])
    plt.plot(start[0], start[1], 'ro', markersize=10);
    plt.plot(goal[0], goal[1], 'ro', color='green', markersize=10);
    plt.xlabel('X')
    plt.ylabel('Y')
    ax = plt.gca()
    for pose in obstacles_poses:
        circle = plt.Circle(pose, R_obstacles, color='yellow')
        ax.add_artist(circle)
    # Create a Rectangle patch
    # rect = patches.Rectangle((0.1,0.1),0.5,0.5,linewidth=1,edgecolor='r',fill='True')
    # ax.add_patch(rect)

def draw_robots():
    plt.arrow(current_point[0], current_point[1], V[0], V[1], width=0.01, head_width=0.05, head_length=0.1, fc='k')
    plt.plot(route1[:,0], route1[:,1], 'red', linewidth=2)
    plt.plot(route2[:,0], route2[:,1], '--', linewidth=2)
    plt.plot(route3[:,0], route3[:,1], '--', linewidth=2)
    triangle = plt.Polygon([next_point1, next_point2, next_point3], color='green', fill=False, linewidth=2);
    plt.gca().add_patch(triangle)

def meters2grid(pose_m, nrows=500, ncols=500):
    # [0, 0](m) -> [250, 250]
    # [1, 0](m) -> [250+100, 250]
    # [0,-1](m) -> [250, 250-100]
    pose_on_grid = np.array(pose_m)*100 + np.array([ncols/2, nrows/2])
    return np.array( pose_on_grid, dtype=int)
def grid2meters(pose_grid, nrows=500, ncols=500):
    # [250, 250] -> [0, 0](m)
    # [250+100, 250] -> [1, 0](m)
    # [250, 250-100] -> [0,-1](m)
    pose_meters = ( np.array(pose_grid) - np.array([ncols/2, nrows/2]) ) / 100.0
    return pose_meters

def gradient_planner(f, current_point, end_coords):
    """
    GradientBasedPlanner : This function computes the next_point
    given current location, goal location and potential map, f.
    It also returns mean velocity, V, of the gradient map in current point.
	"""
    [gy, gx] = np.gradient(-f);
    iy, ix = np.array( meters2grid(current_point), dtype=int )
    w = 80 # smoothing window size for gradient-velocity
    vx = np.mean(gx[ix-int(w/2) : ix+int(w/2), iy-int(w/2) : iy+int(w/2)])
    vy = np.mean(gy[ix-int(w/2) : ix+int(w/2), iy-int(w/2) : iy+int(w/2)])
    V = np.array([vx, vy])
    dt = 0.1 / norm(V);
    next_point = current_point + dt*np.array( [vx, vy] );

    return next_point, V

def combined_potential(obstacles_poses, goal, R_obstacles, nrows=500, ncols=500):
    """ Obstacles map """
    obstacles_map = np.zeros((nrows, ncols));
    [x, y] = np.meshgrid(np.arange(ncols), np.arange(nrows))
    for pose in obstacles_poses:
        pose = meters2grid(pose)
        x0 = pose[0]; y0 = pose[1]
        # cylindrical obstacles
        t = ((x - x0)**2 + (y - y0)**2) < (100*R_obstacles)**2
        obstacles_map[t] = True;
    # rectangular obstacles
    obstacles_map[350:, 130:150] = True;
    obstacles_map[130:150, :300] = True;
    """ Repulsive potential """
    goal = meters2grid(goal)
    d = bwdist(obstacles_map==0);
    d2 = (d/100.) + 1; # Rescale and transform distances
    d0 = 2;
    nu = 200;
    repulsive = nu*((1./d2 - 1/d0)**2);
    repulsive [d2 > d0] = 0;
    """ Attractive potential """
    xi = 1/1000.;
    attractive = xi * ( (x - goal[0])**2 + (y - goal[1])**2 );
    """ Combine terms """
    f = attractive + repulsive;
    return f

def move_obstacles(obstacles_poses):
    dx = 0.01;                   dy = 0.01
    obstacles_poses[0][0] += dx; obstacles_poses[0][1] -= dy
    obstacles_poses[1][0] -= dx; obstacles_poses[1][1] -= dy
    obstacles_poses[2][0] -= dx; obstacles_poses[2][1] -= dy
    obstacles_poses[3][0] += dx; obstacles_poses[3][1] += dy
    return obstacles_poses



""" initialization """
animate = 1
max_its = 100
random_map = 1
num_random_obstacles = 7
moving_obstacles = 1
progress_bar = FillingCirclesBar('Simulation Progress', max=max_its)
R_obstacles = 0.1 # [m]
R_swarm     = 0.2 # [m]
start = np.array([-2.0, 2.0]); goal = np.array([2.0, -2.0])
V0 = (goal - start) / norm(goal-start)   # initial movement direction, |V0| = 1
U0 = np.array([-V0[1], V0[0]]) / norm(V0) # perpendicular to initial movement direction, |U0|=1
should_write_movie = 0; movie_file_name = 'output.avi'
movie_writer = get_movie_writer(should_write_movie, 'Simulation Potential Fields', movie_fps=10., plot_pause_len=0.01)

if random_map:
    obstacles_poses = np.random.uniform(low=-2.5, high=2.5, size=(num_random_obstacles,2)) # randomly located obstacles 
else:
    obstacles_poses = [[-2, 1], [1.5, 0.5], [0, 0], [-1.8, -1.8]] # 2D - coordinates [m]




""" Plan route: centroid path """
fig = plt.figure(figsize=(10, 10))
# drones forming equilateral triangle
route1 = start # leader
route2 = route1 - V0*(R_swarm*sqrt(3)/2) + U0*R_swarm/2 # follower
route3 = route1 - V0*(R_swarm*sqrt(3)/2) - U0*R_swarm/2 # follower
current_point = start

with movie_writer.saving(fig, movie_file_name, max_its) if should_write_movie else get_dummy_context_mgr():
    for i in range(max_its):
        if moving_obstacles: obstacles_poses = move_obstacles(obstacles_poses)

        f = combined_potential(obstacles_poses, goal, R_obstacles)
        dist_to_goal = norm(current_point - goal)
        if dist_to_goal < 0.1:
            print('\nReached the goal')
            break
        # drones forming equilateral triangle
        next_point1, V = gradient_planner(f, current_point, goal)
        U = np.array([-V[1], V[0]]) # perpendicular to the movement direction
        # scale_min * triangular formation < triangular formation < scale_max * triangular formation
        scale_min = 0.6; scale_max = 1.5
        if norm(V) < scale_min:
            v = scale_min*V / norm(V); u = scale_min*U / norm(V)
        elif norm(V) > scale_max:
            v = scale_max*V / norm(V); u = scale_max*U / norm(V)
        else:
            v = V; u = U
        next_point2 = next_point1 - v*R_swarm*sqrt(3)/2 + u*R_swarm/2 # follower
        next_point3 = next_point1 - v*R_swarm*sqrt(3)/2 - u*R_swarm/2 # follower

        route1 = np.vstack([route1, next_point1])
        route2 = np.vstack([route2, next_point2])
        route3 = np.vstack([route3, next_point3])

        current_point = next_point1

        progress_bar.next()
        plt.cla()
        draw_map(R_obstacles)
        draw_robots()
        if animate:
            plt.draw()
            plt.pause(0.01)

        if should_write_movie:
                movie_writer.grab_frame()

    print('\nDone')
    progress_bar.finish()
    plt.show()


# TODO:
# local minimum problem (FM2 - algorithm: https://pythonhosted.org/scikit-fmm/)