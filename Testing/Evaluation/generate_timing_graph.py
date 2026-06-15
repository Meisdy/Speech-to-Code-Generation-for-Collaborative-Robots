import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

commands = [
    "Move\n(joint)", "Move\n(linear)", "Gripper", "Teach\npose",
    "Two-step\nseq.", "Pick &\nplace", "Pick &\noffset", "Multi-step\n(5-cmd)",
]

asr   = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 1.4])
llm   = np.array([3.2, 3.3, 3.1, 3.3, 4.0, 5.1, 5.2, 5.0])
exec_ = np.array([1.6, 1.8, 2.1, 0.1, 3.2, 7.8, 7.0, 7.4])

x = np.arange(len(commands))
w = 0.55

plt.rcParams.update({
    "font.family":       "serif",
    "font.size":         9,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "axes.grid.axis":    "y",
    "grid.linewidth":    0.5,
    "grid.alpha":        0.4,
    "figure.dpi":        150,
})

COLORS = {
    "ASR":  "#4C72B0",
    "LLM":  "#DD8452",
    "Exec": "#55A868",
}

fig, ax = plt.subplots(figsize=(6.5, 3.6))

ax.bar(x, asr,   w, label="ASR",         color=COLORS["ASR"])
ax.bar(x, llm,   w, bottom=asr,          label="LLM parsing", color=COLORS["LLM"])
ax.bar(x, exec_, w, bottom=asr+llm,      label="Execution",   color=COLORS["Exec"])

ax.set_xticks(x)
ax.set_xticklabels(commands, fontsize=8)
ax.set_ylabel("Time (s)")
ax.set_ylim(0, 16)
ax.set_xlim(-0.5, len(commands) - 0.5)

ax.legend(
    handles=[
        mpatches.Patch(color=COLORS["ASR"],  label="ASR"),
        mpatches.Patch(color=COLORS["LLM"],  label="LLM parsing"),
        mpatches.Patch(color=COLORS["Exec"], label="Execution"),
    ],
    loc="upper left", frameon=False, fontsize=8, ncol=3,
)

fig.tight_layout()
fig.savefig("timing_chart.pdf", bbox_inches="tight")
print("Done")