# Counterfactual spatial-regime model

The Shanghai counterfactual is a conditional scenario model, not an estimate of historical probability. Its implemented computation has three coupled layers:

1. a 12,000-path aggregate stochastic state model;
2. a five-state explicit regime-switching process;
3. a ten-node spatial control graph solved with unbalanced optimal transport (UOT).

The aggregate state is

$$
X_t=(N_t,C_t,L_t,S_t,P_t,R_t,G_t,O_t),
$$

where the components are active participants, command continuity, communications, supply, public participation, resistance control, suppression control, and organisational loss.

## Explicit regime switching

Each Monte Carlo path carries a discrete state

$$
Z_t\in\{\text{mobilisation},\text{expansion},\text{encirclement},\text{fragmentation},\text{collapse}\}.
$$

Forward transition probabilities are logistic functions of the current aggregate state, external pressure, isolation, and spatial key-node loss. Minimum-day gates make the process semi-Markov in practice: transitions out of the first four states cannot occur before days 2, 5, 8, and 11 respectively. Collapse is absorbing. Regime-specific coefficients feed back into mobilisation, communications, control, command, and organisational loss.

## Spatial control graph

The graph has ten nodes and fourteen bidirectional edges. Each edge has a positive scenario capacity. The direct travel cost is

$$
c_{ij}=\frac{0.05+1.6d_{ij}}{u_{ij}},
$$

where $d_{ij}$ is map distance and $u_{ij}$ is edge capacity. Floyd-Warshall shortest paths produce the all-pairs base cost matrix. Dynamic costs increase when the opposing side controls the route endpoints.

Each node stores resistance strength, suppression strength, and the derived resistance share

$$
q_{i,t}=\frac{r_{i,t}}{r_{i,t}+g_{i,t}}.
$$

Node labels are resistance for $q\ge0.58$, suppression for $q\le0.42$, and contested otherwise. Loss days are first threshold-crossing times computed from node histories; they are not input constants.

## Unbalanced optimal transport

Each day and for each side, the model constructs source mass $a$, strategic demand $b$, and graph cost $C$. It solves

$$
\min_{\Gamma\ge0}\langle C,\Gamma\rangle
+\varepsilon\sum_{ij}\Gamma_{ij}(\log\Gamma_{ij}-1)
+\rho\,\mathrm{KL}(\Gamma\mathbf 1\Vert a)
+\rho\,\mathrm{KL}(\Gamma^T\mathbf 1\Vert b).
$$

The implementation uses generalized Sinkhorn scaling

$$
u\leftarrow\left(\frac{a}{Kv}\right)^\tau,\qquad
v\leftarrow\left(\frac{b}{K^Tu}\right)^\tau,
$$

with

$$
K=\exp(-C/\varepsilon),\qquad \tau=\frac{\rho}{\rho+\varepsilon}.
$$

The configured values are $\varepsilon=0.22$, $\rho=0.90$, tolerance $10^{-8}$, and at most 240 iterations. Resistance and suppression delivery marginals update node strengths. Resulting network communications, supply, headquarters control, and key-node loss feed back into the next aggregate step. Aggregate participants, command, pressure, collapse share, and regime pressure simultaneously feed the next spatial solve.

This is genuine two-way dynamic coupling:

$$
X_t\rightarrow(a_t,b_t,C_t)\rightarrow\Gamma_t\rightarrow Q_{t+1}\rightarrow X_{t+1}.
$$

## Validation and ablations

Generate and validate the model with:

```powershell
npm run simulate:counterfactual
npm run validate:counterfactual
```

The validator requires all 40 daily side-solves to converge, checks nonzero off-diagonal transport, graph integrity, bounded node histories, endogenous and non-identical loss days, normalized regime shares, monotone absorbing collapse, finite UOT mass diagnostics, and measurable effects in three ablations:

- no spatial feedback;
- no cross-node transport;
- no regime switching.

The fixed seed makes the computation reproducible. It does not make the scenario parameters historical estimates. The current output remains conditional on no provincial ally intervention, continued central reinforcement, and sustained pressure on rail, airport, and river access.
