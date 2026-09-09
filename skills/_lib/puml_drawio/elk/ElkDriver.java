/*
 * ElkDriver — lays out a graph with the Eclipse Layout Kernel and prints the
 * result as JSON.
 *
 * ELK ships inside plantuml.jar (org.eclipse.elk.*, plus EMF and Guava), which
 * the diagram toolchain already downloads, so this needs no extra dependency.
 * plantuml.jar bundles no JSON parser, so input uses a trivial line protocol
 * (we own both ends) and only the OUTPUT is JSON — which Java can emit with
 * printf. All emitted values are numbers or caller-supplied ids, so no string
 * escaping is required.
 *
 * INPUT (stdin), one directive per line:
 *   OPT  <key> <value>                        root layout option
 *   NODE <id> <parentId|-> <w> <h>            parents must precede children
 *   PAD  <id> <top> <right> <bottom> <left>   padding (boundary header room)
 *   EDGE <id> <srcId> <tgtId> <lblW> <lblH>   lblW/lblH 0 = no label
 *
 * OUTPUT (stdout): JSON with node geometry (parent-relative, as draw.io wants)
 * and, per edge, the containing node plus start/bend/end points in THAT node's
 * coordinate space. The caller converts to absolute.
 */
import org.eclipse.elk.core.RecursiveGraphLayoutEngine;
import org.eclipse.elk.core.math.ElkPadding;
import org.eclipse.elk.core.options.*;
import org.eclipse.elk.core.util.BasicProgressMonitor;
import org.eclipse.elk.graph.*;
import org.eclipse.elk.graph.util.ElkGraphUtil;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.*;

public class ElkDriver {

    static final Map<String, ElkNode> nodes = new LinkedHashMap<>();
    static final Map<String, ElkEdge> edges = new LinkedHashMap<>();
    static final Map<String, ElkLabel> labels = new LinkedHashMap<>();
    static ElkNode root;

    public static void main(String[] args) throws Exception {
        root = ElkGraphUtil.createGraph();
        root.setProperty(CoreOptions.ALGORITHM, "org.eclipse.elk.layered");
        root.setProperty(CoreOptions.EDGE_ROUTING, EdgeRouting.ORTHOGONAL);
        root.setProperty(CoreOptions.HIERARCHY_HANDLING, HierarchyHandling.INCLUDE_CHILDREN);
        root.setProperty(CoreOptions.DIRECTION, Direction.DOWN);

        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        String line;
        while ((line = in.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] p = line.split("\\s+");
            switch (p[0]) {
                case "OPT":  applyOption(p[1], join(p, 2)); break;
                case "NODE": addNode(p[1], p[2], d(p[3]), d(p[4])); break;
                case "PAD":  addPad(p[1], d(p[2]), d(p[3]), d(p[4]), d(p[5])); break;
                case "MINSIZE": addMinSize(p[1], d(p[2]), d(p[3])); break;
                case "EDGE": addEdge(p[1], p[2], p[3], d(p[4]), d(p[5])); break;
                default: break;
            }
        }

        new RecursiveGraphLayoutEngine().layout(root, new BasicProgressMonitor());
        emit();
    }

    static double d(String s) { return Double.parseDouble(s); }

    static String join(String[] p, int from) {
        StringBuilder sb = new StringBuilder();
        for (int i = from; i < p.length; i++) { if (i > from) sb.append(' '); sb.append(p[i]); }
        return sb.toString();
    }

    static void addNode(String id, String parentId, double w, double h) {
        ElkNode parent = "-".equals(parentId) ? root : nodes.get(parentId);
        if (parent == null) parent = root;
        ElkNode n = ElkGraphUtil.createNode(parent);
        n.setIdentifier(id);
        n.setDimensions(w, h);
        if (w > 0 && h > 0) {
            // leaf: keep the size the caller computed from its text content
            n.setProperty(CoreOptions.NODE_SIZE_CONSTRAINTS, EnumSet.noneOf(SizeConstraint.class));
        }
        nodes.put(id, n);
    }

    static void addPad(String id, double t, double r, double b, double l) {
        ElkNode n = nodes.get(id);
        if (n != null) n.setProperty(CoreOptions.PADDING, new ElkPadding(t, r, b, l));
    }

    /* Guarantees a boundary is wide enough for its own title bar, so a long
       heading cannot wrap down over the nodes inside it. */
    static void addMinSize(String id, double w, double h) {
        ElkNode n = nodes.get(id);
        if (n == null) return;
        /* ELK transposes the minimum-size vector for vertical layout directions
           (it works left-to-right internally and rotates), so swap the axes for
           DOWN/UP to keep (w, h) meaning what the caller expects. */
        Direction dir = root.getProperty(CoreOptions.DIRECTION);
        boolean vertical = (dir == Direction.DOWN || dir == Direction.UP);
        n.setProperty(CoreOptions.NODE_SIZE_MINIMUM,
            vertical ? new org.eclipse.elk.core.math.KVector(h, w)
                     : new org.eclipse.elk.core.math.KVector(w, h));
        n.setProperty(CoreOptions.NODE_SIZE_CONSTRAINTS,
            EnumSet.of(SizeConstraint.MINIMUM_SIZE, SizeConstraint.NODE_LABELS));
    }

    static void addEdge(String id, String src, String tgt, double lw, double lh) {
        ElkNode s = nodes.get(src), t = nodes.get(tgt);
        if (s == null || t == null) return;
        ElkEdge e = ElkGraphUtil.createSimpleEdge(s, t);
        e.setIdentifier(id);
        edges.put(id, e);
        if (lw > 0 && lh > 0) {
            ElkLabel lbl = ElkGraphUtil.createLabel("x", e);
            lbl.setDimensions(lw, lh);
            lbl.setIdentifier(id);
            labels.put(id, lbl);
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    static void applyOption(String key, String value) {
        switch (key) {
            case "direction":
                root.setProperty(CoreOptions.DIRECTION, Direction.valueOf(value)); break;
            case "edgeRouting":
                root.setProperty(CoreOptions.EDGE_ROUTING, EdgeRouting.valueOf(value)); break;
            case "spacing.nodeNode":
                root.setProperty(CoreOptions.SPACING_NODE_NODE, d(value)); break;
            case "spacing.edgeNode":
                root.setProperty(CoreOptions.SPACING_EDGE_NODE, d(value)); break;
            case "spacing.edgeEdge":
                root.setProperty(CoreOptions.SPACING_EDGE_EDGE, d(value)); break;
            case "spacing.edgeLabel":
                root.setProperty(CoreOptions.SPACING_EDGE_LABEL, d(value)); break;
            case "layered.spacing.nodeNodeBetweenLayers":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.SPACING_NODE_NODE_BETWEEN_LAYERS,
                    d(value)); break;
            case "layered.thoroughness":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.THOROUGHNESS,
                    Integer.valueOf(value)); break;
            case "layered.nodePlacement.strategy":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.NODE_PLACEMENT_STRATEGY,
                    org.eclipse.elk.alg.layered.options.NodePlacementStrategy.valueOf(value)); break;
            case "layered.cycleBreaking.strategy":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.CYCLE_BREAKING_STRATEGY,
                    org.eclipse.elk.alg.layered.options.CycleBreakingStrategy.valueOf(value)); break;
            case "edgeLabels.placement":
                root.setProperty(CoreOptions.EDGE_LABELS_PLACEMENT,
                    EdgeLabelPlacement.valueOf(value)); break;
            case "layered.edgeLabels.sideSelection":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.EDGE_LABELS_SIDE_SELECTION,
                    org.eclipse.elk.alg.layered.options.EdgeLabelSideSelection.valueOf(value)); break;
            case "layered.considerModelOrder.strategy":
                root.setProperty(
                    org.eclipse.elk.alg.layered.options.LayeredOptions.CONSIDER_MODEL_ORDER_STRATEGY,
                    org.eclipse.elk.alg.layered.options.OrderingStrategy.valueOf(value)); break;
            case "separateConnectedComponents":
                root.setProperty(CoreOptions.SEPARATE_CONNECTED_COMPONENTS,
                    Boolean.valueOf(value)); break;
            default: break;   // unknown options are ignored on purpose
        }
    }

    static void emit() {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n \"root\": {\"w\": ").append(fmt(root.getWidth()))
          .append(", \"h\": ").append(fmt(root.getHeight())).append("},\n");

        sb.append(" \"nodes\": {");
        boolean first = true;
        for (Map.Entry<String, ElkNode> e : nodes.entrySet()) {
            ElkNode n = e.getValue();
            if (!first) sb.append(",");
            first = false;
            sb.append("\n  \"").append(e.getKey()).append("\": [")
              .append(fmt(n.getX())).append(",").append(fmt(n.getY())).append(",")
              .append(fmt(n.getWidth())).append(",").append(fmt(n.getHeight())).append("]");
        }
        sb.append("\n },\n \"edges\": {");

        first = true;
        for (Map.Entry<String, ElkEdge> e : edges.entrySet()) {
            ElkEdge edge = e.getValue();
            if (edge.getSections().isEmpty()) continue;
            ElkEdgeSection s = edge.getSections().get(0);
            ElkNode container = edge.getContainingNode();
            String cid = (container == null || container == root || container.getIdentifier() == null)
                ? "-" : container.getIdentifier();
            if (!first) sb.append(",");
            first = false;
            sb.append("\n  \"").append(e.getKey()).append("\": {\"container\": \"").append(cid)
              .append("\", \"start\": [").append(fmt(s.getStartX())).append(",").append(fmt(s.getStartY()))
              .append("], \"bends\": [");
            boolean fb = true;
            for (ElkBendPoint b : s.getBendPoints()) {
                if (!fb) sb.append(",");
                fb = false;
                sb.append("[").append(fmt(b.getX())).append(",").append(fmt(b.getY())).append("]");
            }
            sb.append("], \"end\": [").append(fmt(s.getEndX())).append(",").append(fmt(s.getEndY()))
              .append("]");
            ElkLabel lbl = labels.get(e.getKey());
            if (lbl != null) {
                sb.append(", \"label\": [").append(fmt(lbl.getX())).append(",").append(fmt(lbl.getY()))
                  .append(",").append(fmt(lbl.getWidth())).append(",").append(fmt(lbl.getHeight()))
                  .append("]");
            }
            sb.append("}");
        }
        sb.append("\n }\n}");
        System.out.println(sb);
    }

    static String fmt(double v) {
        return String.format(Locale.ROOT, "%.2f", v);
    }
}
