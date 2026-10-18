import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import type { ComponentType } from "react";
import type { PlotParams } from "react-plotly.js";

const factory = ((createPlotlyComponent as any).default || createPlotlyComponent) as (plotly: any) => ComponentType<PlotParams>;
const Plot = factory(Plotly);

export default Plot;
