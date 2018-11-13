import logging

import requests
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from api_test.common.common import record_dynamic
from api_test.models import Project, ApiInfo, ApiHead, ApiParameter, ApiParameterRaw, ApiResponse, ApiGroupLevelFirst, ApiOperationHistory
from django.db import transaction

from api_test.serializers import ApiInfoDeserializer, ApiHeadDeserializer, ApiParameterDeserializer, \
    ApiResponseDeserializer, ApiGroupLevelFirstSerializer

logger = logging.getLogger(__name__)  # 这里使用 __name__ 动态搜索定义的 logger 配置，这里有一个层次关系的知识点。


def swagger_api(url, project, user):
    """
    请求swagger地址，数据解析
    :param url: swagger地址
    :param project: 项目ID
    :param user: 用户model
    :return:
    """
    req = requests.get(url)
    data = req.json()
    apis = data["paths"]
    tags = data["tags"]
    try:
        params = data["definitions"]
    except KeyError:
        pass
    tg = {}
    obj = Project.objects.get(id=project)
    for t in tags:
        tag ={"name" : t["name"],"project_id" : project}
        group_serialize = ApiGroupLevelFirstSerializer(data=tag)
        if group_serialize.is_valid():
            group_serialize.save(project=obj)
            group_id = group_serialize.data.get("id")
            tg.update({t["name"] : group_id})
    for api, m in apis.items():
        requestApi = {
            "project_id": project, "status": True, "mockStatus": True, "code": "", "desc": "",
            "httpType": "HTTP", "responseList": []
        }
        requestApi["apiAddress"] = api
        for requestType, data in m.items():
            requestApi["requestType"] = requestType.upper()
            if "tags" in data:
                logging.error("tags")
                logging.error(tg[data["tags"][0]])
                requestApi["apiGroupLevelFirst_id"] = tg[data["tags"][0]]
            try:
                requestApi["name"] = data["summary"]
            except KeyError:
                logging.error("43")
                pass
            try:
                if data["consumes"][0] == "application/json":
                    requestApi["requestParameterType"] = "form-data"
                else:
                    requestApi["requestParameterType"] = "form-data"
                requestApi["headDict"] = [{"name": "Content-Type", "value": data["consumes"][0]}]
            except KeyError:
                logging.error("52")
                requestApi["requestParameterType"] = "raw"
            if "parameters" in data:
                parameter = []
                for j in data["parameters"]:
                    if j["in"] == "header":
                        logging.error("header57")
                        requestApi["headDict"].append({"name": j["name"], "value": "String"})
                    elif j["in"] == "body":
                        dto = j["name"]
                        logging.error("dto——body " + dto)
                        try:
                            if "description" in j:
                                parameter.append({"name": dto, "value": "", "_type": j["type"],"required": j["required"], "restrict": "", "description": j["description"]})
                            else:
                                parameter.append({"name": dto, "value": "", "_type": j["type"],"required": j["required"], "restrict": "", "description": ""})
                        except:
                            logging.error("body71")
                            pass
                    elif j["in"] == "query":
                        dto = j["name"]
                        logging.error("dto——query " + dto)
                        try:
                            if "description" in j:
                                parameter.append({"name": dto, "value": "", "_type": j["type"],"required": j["required"], "restrict": "", "description": j["description"]})
                            else:
                                parameter.append({"name": dto, "value": "", "_type": j["type"],"required": j["required"], "restrict": "", "description": ""})
                        except:
                            logging.error("query84")
                            pass
                requestApi["requestList"] = parameter
            if "responses" in data:
                response = []
                if "schema" in data["responses"]["200"]:
                    ref = data["responses"]["200"]["schema"]["$ref"]
                    dto = ref.split("/")[2]
                    for key, value in params[dto]["properties"].items():
                        if "description" in value and "type" in value:
                            response.append({"name": key, "value": value["description"], "_type": value["type"],"required": True, "description": value["description"]})
                        else:
                            response.append({"name": key, "value": "", "_type": "String","required": True, "description": ""})
                        if "items" in value:
                            if "$ref" in value["items"]:
                                ref1 = value["items"]["$ref"]
                                dto1 = ref1.split("/")[2]
                                logging.error("dto1 "+dto1)
                                for key1, value1 in params[dto1]["properties"].items():
                                    logging.error("key1 "+key1)
                                    if "description" in value1 and "type" in value1:
                                        response.append({"name": key + "." + key1, "value": value1["description"], "_type": value1["type"],"required": True, "description": value1["description"]})
                                    else:
                                        response.append({"name": key + "." + key1, "value": "", "_type": "String","required": True, "description": ""})
                                    if "items" in value1:
                                        ref2 = value1["items"]["$ref"]
                                        dto2 = ref2.split("/")[2]
                                        logging.error("dto2 "+dto2)
                                        for key2, value2 in params[dto2]["properties"].items():
                                            logging.error("key2 "+key2)
                                            if "description" in value2 and "type" in value2:
                                                response.append({"name":  key + "." +  key1 + "." + key2, "value": value2["description"], "_type": value2["type"],"required": True, "description": value2["description"]})
                                            else:
                                                response.append({"name":  key + "." +  key1 + "." + key2, "value": "", "_type": "String","required": True, "description": ""})
                requestApi["responseList"] = response
        requestApi["userUpdate"] = user.id
        result = add_swagger_api(requestApi, user)


def add_swagger_api(data, user):
    """
    swagger接口写入数据库
    :param data:  json数据
    :param user:  用户model
    :return:
    """
    try:
        obj = Project.objects.get(id=data["project_id"])
        group = ApiGroupLevelFirst.objects.get(id=data["apiGroupLevelFirst_id"])
        try:
            with transaction.atomic():
                serialize = ApiInfoDeserializer(data=data)
                if serialize.is_valid():
                    serialize.save(project=obj,apiGroupLevelFirst=group)
                    api_id = serialize.data.get("id")
                    try:
                        if len(data["headDict"]):
                            for i in data["headDict"]:
                                try:
                                    if i["name"]:
                                        i["api"] = api_id
                                        head_serialize = ApiHeadDeserializer(data=i)
                                        if head_serialize.is_valid():
                                            head_serialize.save(api=ApiInfo.objects.get(id=api_id))
                                except KeyError:
                                    pass
                    except KeyError:
                        pass
                    if data["requestParameterType"] == "form-data":
                        logging.error("form-data_start")
                        try:
                            if len(data["requestList"]):
                                logging.error("form-data_start_num ")
                                for i in data["requestList"]:
                                    logging.error("form-data_into ")
                                    try:
                                        if i["name"]:
                                            i["api"] = api_id
                                            logging.error("form-data_id ")
                                            param_serialize = ApiParameterDeserializer(data=i)
                                            if param_serialize.is_valid():
                                                logging.error("form-data_save ")
                                                param_serialize.save(api=ApiInfo.objects.get(id=api_id))
                                    except KeyError:
                                        pass
                        except KeyError:
                            pass
                    else:
                        try:
                            if len(data["requestList"]):
                                ApiParameterRaw(api=ApiInfo.objects.get(id=api_id), data=data["requestList"]).save()
                        except KeyError:
                            pass
                    try:
                        if len(data["responseList"]):
                            for i in data["responseList"]:
                                try:
                                    if i["name"]:
                                        i["api"] = api_id
                                        response_serialize = ApiResponseDeserializer(data=i)
                                        if response_serialize.is_valid():
                                            response_serialize.save(api=ApiInfo.objects.get(id=api_id))
                                except KeyError:
                                    pass
                    except KeyError:
                        pass
                    record_dynamic(project=data["project_id"],
                                   _type="新增", operationObject="接口", user=user.pk,
                                   data="新增接口“%s”" % data["name"])
                    api_record = ApiOperationHistory(api=ApiInfo.objects.get(id=api_id),
                                                     user=User.objects.get(id=user.pk),
                                                     description="新增接口\"%s\"" % data["name"])
                    api_record.save()
                return True
        except Exception as e:
            logging.exception("error")
            logging.error(e)
            return False
    except ObjectDoesNotExist:
        return False
