import os
import pickle as pickle
import sys
import numpy as np

import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import yaml

import naq_graphs as naq
from naq_graphs import plotting

if len(sys.argv) > 1:
    graph_tpe = sys.argv[-1]
else:
    print("give me a type of graph please!")

params = yaml.full_load(open("graph_params.yaml", "rb"))[graph_tpe]

os.chdir(graph_tpe)

graph = naq.load_graph()
graph = naq.oversample_graph(graph, params)

modes_df = naq.load_modes()
qualities = naq.load_qualities()

linewidth = 1/(params["innerL"]*params["k_a"])
if linewidth < 5e-4:
    linewidth = 5.e-4
plotting.plot_spectra(graph, modes_df, width=linewidth)

fig = plt.figure()
ax = plt.gca()
plotting.plot_ll_curve(
    graph, modes_df, with_legend=False, with_colors=True, with_thresholds=False, ax=ax
)

ll_axis = inset_axes(ax, width="50%", height="50%", borderpad=1, loc="upper left")
plotting.plot_ll_curve(
    graph,
    modes_df,
    with_legend=False,
    with_colors=True,
    with_thresholds=False,
    ax=ll_axis,
)

D0s = modes_df["modal_intensities"].columns.values
top = np.max(modes_df["modal_intensities"].to_numpy()[:, round(0.3*len(D0s))])
ll_axis.axis([D0s[0], D0s[ round(0.3*len(D0s))], -0.01, top ])

ll_axis.tick_params(axis="both", which="major", labelsize=5)
ll_axis.xaxis.label.set_size(8)
ll_axis.yaxis.label.set_size(8)

fig.savefig("ll_curves.png", bbox_inches="tight")

plt.show()

fig, axes = plt.subplots(nrows=2, ncols=1)
fig.subplots_adjust(wspace=0, hspace=0)
plotting.plot_stem_spectra(graph, modes_df, -1, ax=axes[0])
axes[0].set_xticks([])
plotting.plot_scan(graph, qualities, modes_df, ax=axes[1])
plotting.plot_pump_traj(modes_df, with_scatter=False, with_approx=False, ax=axes[1])

fig.savefig("final_plot.png", bbox_inches="tight")
plt.show()

lasing_modes_list = np.where(modes_df["modal_intensities"].to_numpy()[:, -1] > 0)[0]
lasing_modes_ordered = np.argsort(modes_df["modal_intensities"].to_numpy()[:, -1])[::-1]
#### list lasing modes in order of intensity at specific D0 or in order of interacting threshold ####
#lasing_mode_id = lasing_modes_ordered[range(len(lasing_modes_list))]
lasing_mode_id = np.argsort(modes_df["interacting_lasing_thresholds"].to_numpy())
print('lasing modes: ', lasing_mode_id)

fig, axes = plt.subplots(
    # nrows=int(np.ceil(len(lasing_mode_id) / 3.0)), ncols=3, figsize=(12, 4)
    nrows=3,
    ncols=3,
    figsize=(12, 4),
)
for ax, index in zip(axes.flatten(), lasing_mode_id):
    plotting.plot_single_mode(
        graph, modes_df, index, df_entry="threshold_lasing_modes", colorbar=False, ax=ax
    )

fig.savefig("lasing_modes.png", bbox_inches="tight")

plt.show()
