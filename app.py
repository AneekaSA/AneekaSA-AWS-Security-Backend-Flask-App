import boto3
import yaml
import json
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

cf = boto3.client("cloudformation")
ec2 = boto3.client("ec2")


@app.get("/template/<stack_name>")
def get_template(stack_name):
    try:
        response = cf.get_template(StackName=stack_name)
        yaml_template = response["TemplateBody"]
        template_dict = yaml.safe_load(yaml_template)

        return jsonify({
            "stack_name": stack_name,
            "template": template_dict
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.put("/template/modify")
def update_subnet_to_private():
    try:
        template = request.json["template"]
        resources = template.get("Resources", {})
        routes_to_delete = []

        for name, resource in resources.items():
            if resource.get("Type") == "AWS::EC2::Route":
                props = resource.get("Properties", {})
                if (
                    props.get("DestinationCidrBlock") == "0.0.0.0/0"
                    and "GatewayId" in props
                ):
                    routes_to_delete.append(name)

        for r in routes_to_delete:
            del resources[r]

        return jsonify({
            "message": "Subnet converted to private",
            "updated_template": template
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/changeset")
def create_changeset():
    try:
        data = request.json
        stack_name = data["stack_name"]
        template_dict = data["template"]

        template_json = json.dumps(template_dict)
        changeset_name = f"changeset-{int(time.time())}"

        response = cf.create_change_set(
            StackName=stack_name,
            TemplateBody=template_json,
            ChangeSetName=changeset_name,
            ChangeSetType="UPDATE",
            Capabilities=["CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"]
        )

        changeset_id = response["Id"]

        while True:
            status = cf.describe_change_set(ChangeSetName=changeset_id, StackName=stack_name)
            state = status["Status"]

            if state in ["CREATE_COMPLETE", "FAILED"]:
                break

            time.sleep(2)

        return jsonify({
            "message": "ChangeSet creation finished",
            "changeset_id": changeset_id,
            "status": state,
            "status_reason": status.get("StatusReason", "OK")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
