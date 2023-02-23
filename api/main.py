import base64
import json
import pickle

import classifiers
import numpy
from db import conn
from flask import Flask, request

app = Flask(__name__)

cur = conn.cursor()
cur.execute(
    """create table if not exists models(
        ID int primary key auto_increment,
        model_name varchar(50) not null,
        params text not null,
        dimension int not null,
        num_classes int not null,
        classifier blob not null,
        num_trained int not null default 0
    );"""
)


@app.route("/health/", methods=["GET"])
def report_api_health():
    return {"status": "ok"}, 200


@app.route("/models/", methods=["POST"])
def create_model():
    try:
        model = request.json["model"]
        params = request.json["params"]
        d = request.json["d"]
        n_classes = request.json["n_classes"]
    except KeyError:
        return {"status": "Malformed request"}, 400
    if not isinstance(params, dict):
        return {"status": "Malformed request"}, 400
    params_jsonified = json.dumps(params)
    try:
        model_cls = getattr(classifiers, model)
    except AttributeError:
        return {"status": "Nonexistent model"}, 400
    classifier = model_cls(**params)
    classifier_pickled = pickle.dumps(classifier)
    cur.execute(
        """insert into models (model_name, params, dimension, num_classes, classifier)
        values (%s, %s, %s, %s, %s);""",
        (model, params_jsonified, d, n_classes, classifier_pickled),
    )
    conn.commit()
    return {"id": cur.lastrowid}, 201


@app.route("/models/<int:model_id>/", methods=["GET"])
def get_model(model_id):
    cur.execute("""select * from models where ID = %s;""", (model_id,))
    try:
        _, model, params_jsonified, d, n_classes, _, n_trained = cur.fetchone()
    except Exception:
        return {"status": "Not found"}, 404
    return {
        "model": model,
        "params": json.loads(params_jsonified),
        "d": d,
        "n_classes": n_classes,
        "n_trained": n_trained,
    }, 200


@app.route("/models/<int:model_id>/train/", methods=["POST"])
def train_model(model_id):
    cur.execute("""select * from models where ID = %s;""", (model_id,))
    try:
        _, _, _, d, n_classes, classifier_pickled, n_trained = cur.fetchone()
    except Exception:
        return {"status": "Not found"}, 404
    try:
        x = numpy.asarray(request.json["x"]).reshape(1, -1)
        y = request.json["y"]
    except KeyError:
        return {"status": "Malformed request"}, 400
    if not isinstance(y, int):
        return {"status": "Malformed request"}, 400
    if y >= n_classes:
        return {"status": "Malformed request"}, 400
    if x.size != d:
        return {"status": "Malformed request"}, 400
    classifier = pickle.loads(classifier_pickled)
    classifier = classifier.partial_fit(x, numpy.atleast_1d(y), classes=numpy.asarray(range(n_classes)))
    classifier_pickled = pickle.dumps(classifier)
    n_trained += 1
    cur.execute(
        """update models set classifier = %s, num_trained = %s where ID = %s;""",
        (classifier_pickled, n_trained, model_id),
    )
    conn.commit()
    return {"id": model_id}, 200


@app.route("/models/<int:model_id>/predict/", methods=["GET"])
def predict_with_model(model_id):
    cur.execute("""select * from models where ID = %s;""", (model_id,))
    try:
        _, _, _, d, _, classifier_pickled, _ = cur.fetchone()
    except Exception:
        return {"status": "Not found"}, 404
    if "x" not in request.args:
        return {"status": "Malformed request"}, 400
    xb64 = request.args["x"]
    x_list = eval(base64.b64decode(xb64.encode("ascii")).decode("ascii"))
    x = numpy.asarray(x_list).reshape(1, -1)
    if x.size != d:
        return {"status": "Malformed request"}, 400
    classifier = pickle.loads(classifier_pickled)
    y_pred = classifier.predict(x)
    return {"x": x_list, "y": y_pred.item()}, 200


@app.route("/models/", methods=["GET"])
def get_models_with_training_scores():
    def normalizer(val, min_, max_):
        # Discrete (step) normalizer with step = 0.5 and epsilon = 0.1
        distance = max_ - min_
        if distance == 0:
            return 1.0
        if (val - min_) / distance < 0.1:
            return 0.0
        if (max_ - val) / distance < 0.1:
            return 1.0
        return 0.5

    models = []
    model_names = ["SGDClassifier", "CategoricalNB", "MLPClassifier"]
    for model_name in model_names:
        cur.execute(
            """select ID, model_name, num_trained from models where model_name = %s order by num_trained;""",
            (model_name,),
        )
        results = cur.fetchall()
        lowest_val, highest_val = results[0][2], results[-1][2]
        for entry in results:
            models.append(
                {
                    "id": entry[0],
                    "model": entry[1],
                    "n_trained": entry[2],
                    "training_score": normalizer(entry[2], lowest_val, highest_val),
                }
            )
    return {"models": models}, 200


@app.route("/models/groups/", methods=["GET"])
def get_groups_of_models():
    groups = []
    cur.execute("""select num_trained, JSON_ARRAYAGG(ID) from models group by num_trained;""")
    for group in cur.fetchall():
        n_trained, model_ids = group
        groups.append({"n_trained": n_trained, "model_ids": eval(model_ids)})
    return {"groups": groups}, 200
