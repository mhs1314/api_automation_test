import logging

import requests
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from api_test.common.common import record_dynamic
from api_test.models import Project, ApiInfo, ApiHead, ApiParameter, ApiParameterRaw, ApiResponse, ApiOperationHistory
from django.db import transaction

from api_test.serializers import ApiInfoDeserializer, ApiHeadDeserializer, ApiParameterDeserializer, \
    ApiResponseDeserializer

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
    try:
        params = data["definitions"]
    except KeyError:
        pass
    for api, m in apis.items():
        requestApi = {
            "project_id": project, "status": True, "mockStatus": "200", "code": "", "desc": "",
            "httpType": "HTTP", "responseList": []
        }
        requestApi["apiAddress"] = api
        for requestType, data in m.items():
            requestApi["requestType"] = requestType.upper()
            try:
                requestApi["name"] = data["summary"]
            except KeyError:
                pass
            try:
                if data["consumes"][0] == "application/json":
                    requestApi["requestParameterType"] = "form-data"
                else:
                    requestApi["requestParameterType"] = "form-data"
                requestApi["headDict"] = [{"name": "Content-Type", "value": data["consumes"][0]}]
            except KeyError:
                pass
            for j in data["parameters"]:
                if j["in"] == "header":
                    requestApi["headDict"].append({"name": j["name"], "value": "String"})
                elif j["in"] == "body":
                    dto = j["name"][:1].upper() + j["name"][1:]
                    try:
                        if requestApi["requestParameterType"] == "raw":
                            parameter = {}
                            for key, value in params[dto]["properties"].items():
                                parameter[key] = value['type']
                                requestApi["requestList"] = str(parameter)
                        else:
                            parameter = []
                            for key, value in params[dto]["properties"].items():
                                if  value["description"]:
                                    parameter.append({"name": key, "value": value["name"], "_type": value["tyep"],
                                                  "required": True, "restrict": "", "description": value["description"]})
                                else:
                                    parameter.append({"name": key, "value": value["name"], "_type": value["tyep"],
                                                  "required": True, "restrict": "", "description": ""]})
                            requestApi["requestList"] = parameter
                        # print(requestApi)
                    except:
                        pass
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
        try:
            with transaction.atomic():
                serialize = ApiInfoDeserializer(data=data)
                if serialize.is_valid():
                    serialize.save(project=obj)
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
                        try:
                            if len(data["requestList"]):
                                for i in data["requestList"]:
                                    try:
                                        if i["name"]:
                                            i["api"] = api_id
                                            param_serialize = ApiParameterDeserializer(data=i)
                                            if param_serialize.is_valid():
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
