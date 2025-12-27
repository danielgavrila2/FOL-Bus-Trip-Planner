def generate_fol(stops, connections, start, goal):
    f = []
    f.append("set(production).")
    f.append("formulas(assumptions).")
    f.append(f"start({start}).")
    f.append(f"goal({goal}).")

    for stop in stops:
        f.append(f"stop({stop}).")

    for conn in connections:
        f.append(f"connects({conn['from']}, {conn['to']}, {conn['line']}).")

    f.append("end_of_list.")

    f.append("formulas(productions).")
    f.append("start(S) -> visited(S).")
    f.append("visited(X) & connects(X,Y,L) & ~visited(Y) -> visited(Y), take(X,Y,L).")
    f.append("end_of_list.")

    return "\n".join(f)