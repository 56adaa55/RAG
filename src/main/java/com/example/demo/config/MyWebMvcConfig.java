package com.example.demo.config;

import com.alibaba.fastjson.serializer.SerializerFeature;
import com.alibaba.fastjson.support.config.FastJsonConfig;
import com.alibaba.fastjson.support.spring.FastJsonHttpMessageConverter;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.convert.support.GenericConversionService;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.bind.support.ConfigurableWebBindingInitializer;
import org.springframework.web.servlet.config.annotation.ContentNegotiationConfigurer;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurationSupport;
import org.springframework.web.servlet.mvc.method.annotation.RequestMappingHandlerAdapter;

import javax.annotation.PostConstruct;
import java.nio.charset.Charset;
import java.util.List;


//import com.alibaba.fastjson.serializer.SerializerFeature;
//import com.alibaba.fastjson.support.config.FastJsonConfig;
//import com.alibaba.fastjson.support.spring.FastJsonHttpMessageConverter;

//@SuppressWarnings("deprecation")
//springboot 2.0配置WebMvcConfigurationSupport之后，会导致默认配置被覆盖，要访问静态资源需要重写addResourceHandlers方法
@Configuration
public class MyWebMvcConfig   extends WebMvcConfigurationSupport {  // implements WebMvcConfigurer{  
	
	    //String basePath = new ApplicationHome(this.getClass()).getSource().getParentFile().getPath()+ "/files/";
		
		String basePath;

		@Autowired
		private RequestMappingHandlerAdapter handlerAdapter;
	
	    //自定义响应数据String的编码
	    @Bean
	    public HttpMessageConverter<String> responseBodyConverter() {
	        StringHttpMessageConverter converter = new StringHttpMessageConverter(
	                Charset.forName("UTF-8"));
	        return converter;
	    }
	    
	    
	   //自定义响应数据Json的编码及格式
		/*
	    @Bean
	    public FastJsonHttpMessageConverter fastJsonHttpMessageConverter() {
	    	FastJsonHttpMessageConverter converter = new FastJsonHttpMessageConverter();
	    	FastJsonConfig config = new FastJsonConfig();
	    	config.setDateFormat("yyyy-MM-dd HH:mm:ss");
	    	config.setCharset(Charset.forName("UTF-8"));
	    	config.setSerializerFeatures(SerializerFeature.WriteClassName,SerializerFeature.WriteMapNullValue,SerializerFeature.PrettyFormat,SerializerFeature.WriteNullListAsEmpty,SerializerFeature.WriteNullStringAsEmpty);
	    	converter.setFastJsonConfig(config);
	    	return converter;
	    }
		*/
	    
	    @Override
	    public void configureMessageConverters(List<HttpMessageConverter<?>> converters) {
	        super.configureMessageConverters(converters);
	        converters.add(responseBodyConverter());
	        converters.add(new MappingJackson2HttpMessageConverter());
	        //converters.add(fastJsonHttpMessageConverter());

	    }
	    @Override
	    public void configureContentNegotiation(ContentNegotiationConfigurer configurer) {
	        configurer.favorPathExtension(false);
	    }

		/**
		 * 此方法解决前台提交的日期参数绑定不正确问题,将自己实现的StringToDateConverter交给spring,让其知道如何进行处理
		 */
		/*
		@PostConstruct //@PostContruct是spring框架的注解，在方法上加该注解会在项目启动的时候执行该方法，也可以理解为在spring容器初始化的时候执行该方法。
		public void initEditableValidation() {
			ConfigurableWebBindingInitializer initializer = (ConfigurableWebBindingInitializer) handlerAdapter.getWebBindingInitializer();
			if (initializer.getConversionService() != null) {
				GenericConversionService genericConversionService = (GenericConversionService) initializer.getConversionService();
				genericConversionService. .addConverter(new StringToDateConverter());
			}
		}
		*/


		//自定义静态资源访问路径
	    @Override
	    public void addResourceHandlers(ResourceHandlerRegistry registry) {
	    	registry.addResourceHandler("/**")
             //.addResourceLocations("classpath:/resources/")
             .addResourceLocations("classpath:/static/")
             .addResourceLocations("classpath:/public/");
	    	 
	        registry.addResourceHandler("/static/**").addResourceLocations("classpath:/static/");
	        //SAVEPATH就是上面的basePath，当请求Url包含static/files/时，就会以文件路径来访问basePath下面的文件
	        registry.addResourceHandler("static/files/**").addResourceLocations("file:" + basePath);
	        
	        registry.addResourceHandler("swagger-ui.html")
            .addResourceLocations("classpath:/META-INF/resources/");

	        registry.addResourceHandler("/webjars/**")
            .addResourceLocations("classpath:/META-INF/resources/webjars/");

	        
	        super.addResourceHandlers(registry);
	    }
	

	    //自定义动态页面关联
	    
	    
	    //自定义拦截器
	    //
	    @Override
	    public void addInterceptors(InterceptorRegistry registry) {
	    	/*
	        registry.addInterceptor(new MyInterceptor1())
	                .addPathPatterns("/**")
	                .excludePathPatterns("/hello");
	    	*/
	    }	
	 	
	    
	    
	  
}
